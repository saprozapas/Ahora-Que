"""Encuestas de grupo: armar un plan entre todos.

Flujo (columna "Grupo_Encuesta"."Estado"):

    abierta
        Cada integrante responde SUS filtros (precio máximo, restricciones,
        tipos de lugar) y cuándo puede (hasta 3 franjas con día y horas).
        Se pasa a "eligiendo" cuando respondieron todos, o antes si quien
        creó la encuesta la cierra. En ese momento:
          - se calcula el horario donde puede más gente (elegir_horario);
          - se arman OPCIONES_POR_RONDA planes distintos con los filtros
            combinados (combinar_respuestas).
    eligiendo
        Cada integrante vota UNA opción o "ninguna me convence". Se resuelve
        cuando votaron todos, o antes si el creador cierra la elección:
          - gana "ninguna" (más votos que cualquier opción): se arman otros
            planes (sin repetir lugares) y se vota de nuevo;
          - empate entre opciones: se vota de nuevo entre las más votadas
            (máximo 2). Si vuelve a empatar, se elige una al azar;
          - gana una opción: se crea el plan en "votacion" y sigue el flujo
            normal del grupo (ver GrupoPlanService). Los que votaron esa
            opción ya quedan con su "me gusta" y su "puedo" cargados.
    cerrada / cancelada

Para ajustar cómo se combinan los filtros, tocar combinar_respuestas().
"""

import random
from collections import Counter
from datetime import date, datetime

import psycopg2
from psycopg2.extras import Json

from database import get_db_connection, release_db_connection
from ia_bridge import tipos_por_lugar
from services.grupo_plan_service import GrupoPlanError, GrupoPlanService
from services.lugar_service import LugarService
from services.plan_reglas import roles_de, validar
from services.precio_lugar import RANGOS_POR_NIVEL, rango_de_nivel, sumar_rangos

# Cuántas paradas puede tener como máximo un plan armado por encuesta.
MAX_PARADAS = 3
# Cuántas paradas se arman si nadie eligió ningún tipo.
PARADAS_SIN_TIPOS = 2
# Cuántos planes se ofrecen en cada ronda, y cuántos intentos se hacen para
# encontrarlos (los lugares se sortean, a veces salen repetidos).
OPCIONES_POR_RONDA = 3
MAX_INTENTOS = 10
# Franjas de disponibilidad que puede cargar cada integrante.
MAX_FRANJAS = 3

# Campos de la respuesta que son restricciones (se suman: si uno la pide, vale).
RESTRICCIONES = ("apto_menores", "opcion_celiacos", "opcion_vegana")


def opciones_de_precio():
    """[(nivel, "$100 - $300"), ...] a partir de precio_lugar.RANGOS_POR_NIVEL,
    para que el monto que se muestra sea siempre el que usa el código."""
    return [
        (nivel, f"${minimo:g} - ${maximo:g}")
        for nivel, (minimo, maximo) in sorted(RANGOS_POR_NIVEL.items())
        if nivel > 0
    ]


def combinar_respuestas(respuestas):
    """Junta las respuestas de todos en filtros para el buscador de lugares.

    respuestas: lista de dicts con nivel_precio (int o None), apto_menores,
    opcion_celiacos, opcion_vegana (bool) y tipos (lista de ids).

    Devuelve (filtros, tipos): `filtros` con las mismas claves que
    FILTROS_LUGAR (services/lugar_filtros.py) y `tipos` ordenados de más a
    menos elegidos. Gana el más restrictivo."""
    filtros = {}

    niveles = [r["nivel_precio"] for r in respuestas if r.get("nivel_precio")]
    if niveles:
        filtros["nivel_precio"] = str(min(niveles))

    for campo in RESTRICCIONES:
        if any(r.get(campo) for r in respuestas):
            filtros[campo] = "1"

    votos_por_tipo = Counter(t for r in respuestas for t in r.get("tipos", []))
    tipos = [tipo for tipo, _ in votos_por_tipo.most_common()]
    return filtros, tipos


def elegir_horario(disponibilidades):
    """El (fecha, hora, usuarios) donde puede más gente.

    disponibilidades: [{"user", "fecha", "desde", "hasta"}]. Los horarios
    candidatos son los "desde" de cada franja; en un empate gana el más
    temprano. Devuelve None si no hay franjas."""
    mejor = None
    for fecha, hora in sorted({(d["fecha"], d["desde"]) for d in disponibilidades}):
        pueden = {
            d["user"] for d in disponibilidades
            if d["fecha"] == fecha and d["desde"] <= hora < d["hasta"]
        }
        if mejor is None or len(pueden) > len(mejor[2]):
            mejor = (fecha, hora, pueden)
    return mejor


def elegir_lugares(buscar, roles_por_lugar, filtros, tipos, excluir=()):
    """Arma las paradas de UN plan. Una parada por tipo (en orden de
    popularidad) o, si nadie eligió tipos, PARADAS_SIN_TIPOS al azar.
    Se salta los lugares que dejarían el plan incoherente (plan_reglas) y los
    ids de `excluir`.

    buscar(tipo_id, filtros) -> lista de lugares (dicts con id y nombre).
    roles_por_lugar(lugares) -> {id: [roles]}.
    Se reciben como parámetros para poder probarlo sin base de datos."""
    objetivos = list(tipos[:MAX_PARADAS]) or [""] * PARADAS_SIN_TIPOS
    elegidos = []
    for tipo in objetivos:
        candidatos = [c for c in buscar(tipo, filtros) if c["id"] not in excluir]
        roles = roles_por_lugar(candidatos)
        for lugar in candidatos:
            if any(e["id"] == lugar["id"] for e in elegidos):
                continue
            lugar = {**lugar, "roles": roles.get(lugar["id"], [])}
            if not validar(elegidos + [lugar]):
                elegidos.append(lugar)
                break
    return elegidos


def armar_opciones(generar, ya_usados=frozenset(), cantidad=OPCIONES_POR_RONDA,
                   intentos=MAX_INTENTOS):
    """Varios planes DISTINTOS entre sí y de `ya_usados` (combinaciones de ids
    de lugares de rondas anteriores).

    generar(excluir_ids) -> lista de lugares de un plan (puede venir vacía).
    En la primera mitad de los intentos se evitan además los lugares ya
    ofrecidos; en la segunda solo se evita repetir la combinación exacta."""
    combos = {frozenset(c) for c in ya_usados}
    lugares_vistos = {i for c in combos for i in c}
    opciones = []
    for intento in range(intentos):
        if len(opciones) >= cantidad:
            break
        excluir = lugares_vistos if intento < intentos // 2 else {
            i for o in opciones for i in (l["id"] for l in o)}
        lugares = generar(set(excluir))
        if not lugares:
            continue
        clave = frozenset(l["id"] for l in lugares)
        if clave in combos:
            continue
        combos.add(clave)
        opciones.append(lugares)
    return opciones


class GrupoEncuestaService:

    def __init__(self):
        self._lugares = LugarService()
        self._plan_grupo = GrupoPlanService()

    # --- Helpers ------------------------------------------------------------

    def _es_miembro(self, cursor, group_id, user_id):
        cursor.execute(
            'SELECT 1 FROM public."Usuario-Grupo" WHERE "Id_Grupo" = %s AND "Id_Usuario" = %s',
            (group_id, user_id),
        )
        if cursor.fetchone() is None:
            raise GrupoPlanError("No sos integrante de este grupo.")

    def _datos(self, cursor, encuesta_id, group_id, user_id, estados):
        """Bloquea la encuesta y devuelve sus datos si es de ese grupo, el
        usuario es integrante y está en alguno de los `estados`."""
        self._es_miembro(cursor, group_id, user_id)
        cursor.execute(
            """
            SELECT "Creado_Por", "Titulo", "Fecha_Plan", "Hora_Plan", "Estado", "Ronda", "Es_Desempate"
            FROM public."Grupo_Encuesta"
            WHERE "Id_Encuesta" = %s AND "Id_Grupo" = %s
            FOR UPDATE
            """,
            (encuesta_id, group_id),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise GrupoPlanError("Esa encuesta no es de este grupo.")
        if fila[4] not in estados:
            raise GrupoPlanError("Esa encuesta ya no está en esa etapa.")
        return {"creado_por": fila[0], "titulo": fila[1], "fecha": fila[2], "hora": fila[3],
                "estado": fila[4], "ronda": fila[5], "desempate": fila[6]}

    def _estado(self, encuesta_id, group_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT "Estado" FROM public."Grupo_Encuesta" WHERE "Id_Encuesta" = %s AND "Id_Grupo" = %s',
                    (encuesta_id, group_id),
                )
                fila = cursor.fetchone()
            if fila is None:
                raise GrupoPlanError("Esa encuesta no es de este grupo.")
            return fila[0]
        finally:
            release_db_connection(connection)

    def _miembros(self, cursor, group_id):
        cursor.execute('SELECT COUNT(*) FROM public."Usuario-Grupo" WHERE "Id_Grupo" = %s', (group_id,))
        return cursor.fetchone()[0]

    def _respuestas(self, cursor, encuesta_id):
        cursor.execute(
            """
            SELECT "Nivel_Precio_Max", "Apto_Menores", "Opcion_Celiacos", "Opcion_Vegana", "Tipos"
            FROM public."Grupo_Encuesta_Respuesta" WHERE "Id_Encuesta" = %s
            """,
            (encuesta_id,),
        )
        return [
            {"nivel_precio": f[0], "apto_menores": f[1], "opcion_celiacos": f[2],
             "opcion_vegana": f[3], "tipos": list(f[4] or [])}
            for f in cursor.fetchall()
        ]

    def _disponibilidades(self, cursor, encuesta_id):
        cursor.execute(
            'SELECT "Id_Usuario", "Fecha", "Desde", "Hasta" FROM public."Grupo_Encuesta_Disponibilidad" WHERE "Id_Encuesta" = %s',
            (encuesta_id,),
        )
        return [{"user": str(f[0]), "fecha": f[1], "desde": f[2], "hasta": f[3]} for f in cursor.fetchall()]

    def _roles(self, candidatos):
        tipos = tipos_por_lugar([c["id"] for c in candidatos])
        return {c["id"]: roles_de(c["nombre"], tipos.get(c["id"], [])) for c in candidatos}

    # --- Crear ----------------------------------------------------------------

    def crear(self, group_id, user_id, titulo):
        titulo = (titulo or "").strip()
        if not titulo:
            raise GrupoPlanError("El plan necesita un nombre.")
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                self._es_miembro(cursor, group_id, user_id)
                cursor.execute(
                    """
                    INSERT INTO public."Grupo_Encuesta" ("Id_Grupo", "Creado_Por", "Titulo")
                    VALUES (%s, %s, %s)
                    RETURNING "Id_Encuesta"
                    """,
                    (group_id, user_id, titulo),
                )
                encuesta_id = cursor.fetchone()[0]
            connection.commit()
            return encuesta_id
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Responder (filtros + disponibilidad) -----------------------------------

    def responder(self, group_id, encuesta_id, user_id, nivel_precio, apto_menores,
                  celiacos, vegana, tipos, franjas):
        """Guarda (o cambia) la respuesta. `franjas`: [(fecha, desde, hasta)]
        con date/time. Si con ésta ya respondieron todos, se arman las
        opciones. Devuelve 'opciones', 'sin_lugares' (respondieron todos pero
        no hay lugares que cumplan: la encuesta sigue abierta) o None."""
        if not franjas:
            raise GrupoPlanError("Cargá al menos un día y horario en el que puedas.")
        if len(franjas) > MAX_FRANJAS:
            raise GrupoPlanError(f"Podés cargar hasta {MAX_FRANJAS} horarios.")
        ahora = datetime.now()
        for fecha, desde, hasta in franjas:
            if hasta <= desde:
                raise GrupoPlanError("En cada horario, el «hasta» tiene que ser después del «desde».")
            if datetime.combine(fecha, hasta) <= ahora:
                raise GrupoPlanError("Elegí horarios que todavía no pasaron.")

        tipos_validos = {str(t["id"]) for t in self._lugares.listar_tipos()}
        tipos = [str(t) for t in tipos if str(t) in tipos_validos]

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                self._datos(cursor, encuesta_id, group_id, user_id, ("abierta",))
                cursor.execute(
                    """
                    INSERT INTO public."Grupo_Encuesta_Respuesta"
                        ("Id_Encuesta", "Id_Usuario", "Nivel_Precio_Max", "Apto_Menores",
                         "Opcion_Celiacos", "Opcion_Vegana", "Tipos")
                    VALUES (%s, %s, %s, %s, %s, %s, %s::text[])
                    ON CONFLICT ("Id_Encuesta", "Id_Usuario") DO UPDATE SET
                        "Nivel_Precio_Max" = EXCLUDED."Nivel_Precio_Max",
                        "Apto_Menores" = EXCLUDED."Apto_Menores",
                        "Opcion_Celiacos" = EXCLUDED."Opcion_Celiacos",
                        "Opcion_Vegana" = EXCLUDED."Opcion_Vegana",
                        "Tipos" = EXCLUDED."Tipos",
                        "Respondida_En" = now()
                    """,
                    (encuesta_id, user_id, nivel_precio, apto_menores, celiacos, vegana, tipos),
                )
                cursor.execute(
                    'DELETE FROM public."Grupo_Encuesta_Disponibilidad" WHERE "Id_Encuesta" = %s AND "Id_Usuario" = %s',
                    (encuesta_id, user_id),
                )
                for fecha, desde, hasta in franjas:
                    cursor.execute(
                        """
                        INSERT INTO public."Grupo_Encuesta_Disponibilidad"
                            ("Id_Encuesta", "Id_Usuario", "Fecha", "Desde", "Hasta")
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (encuesta_id, user_id, fecha, desde, hasta),
                    )
                cursor.execute(
                    'SELECT COUNT(*) FROM public."Grupo_Encuesta_Respuesta" WHERE "Id_Encuesta" = %s',
                    (encuesta_id,),
                )
                respondieron = cursor.fetchone()[0]
                miembros = self._miembros(cursor, group_id)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

        if respondieron < miembros:
            return None
        try:
            return self._cerrar_respuestas(group_id, encuesta_id, user_id)
        except GrupoPlanError:
            return "sin_lugares"

    # --- Cerrar / cancelar ---------------------------------------------------

    def cerrar(self, group_id, encuesta_id, user_id):
        """El creador cierra la etapa en la que esté la encuesta sin esperar a
        todos: arma las opciones (si estaba abierta) o resuelve la elección
        con los votos que haya (si estaba eligiendo)."""
        if self._estado(encuesta_id, group_id) == "abierta":
            return self._cerrar_respuestas(group_id, encuesta_id, user_id, solo_creador=True)
        return self._votar_o_cerrar(group_id, encuesta_id, user_id, cerrar=True)

    def cancelar(self, group_id, encuesta_id, user_id):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                datos = self._datos(cursor, encuesta_id, group_id, user_id, ("abierta", "eligiendo"))
                if str(datos["creado_por"]) != str(user_id):
                    raise GrupoPlanError("Solo quien creó la encuesta puede cancelarla.")
                cursor.execute(
                    'UPDATE public."Grupo_Encuesta" SET "Estado" = \'cancelada\' WHERE "Id_Encuesta" = %s',
                    (encuesta_id,),
                )
            connection.commit()
            return "cancelada"
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def _cerrar_respuestas(self, group_id, encuesta_id, user_id, solo_creador=False):
        """abierta -> eligiendo: calcula el horario y arma la primera ronda.
        Si no hay respuestas o lugares levanta GrupoPlanError y no cambia nada."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                datos = self._datos(cursor, encuesta_id, group_id, user_id, ("abierta",))
                if solo_creador and str(datos["creado_por"]) != str(user_id):
                    raise GrupoPlanError("Solo quien creó la encuesta puede cerrarla.")

                respuestas = self._respuestas(cursor, encuesta_id)
                if not respuestas:
                    raise GrupoPlanError("Todavía nadie respondió la encuesta.")
                horario = elegir_horario(self._disponibilidades(cursor, encuesta_id))
                if horario is None:
                    raise GrupoPlanError("Nadie cargó un horario en el que pueda.")
                fecha, hora, _ = horario

                opciones = self._generar(respuestas, set())
                self._guardar_opciones(cursor, encuesta_id, 1, opciones)
                cursor.execute(
                    """
                    UPDATE public."Grupo_Encuesta"
                    SET "Estado" = 'eligiendo', "Ronda" = 1, "Es_Desempate" = false,
                        "Fecha_Plan" = %s, "Hora_Plan" = %s
                    WHERE "Id_Encuesta" = %s
                    """,
                    (fecha, hora, encuesta_id),
                )
            connection.commit()
            return "opciones"
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Generar opciones --------------------------------------------------------

    def _generar(self, respuestas, ya_usados):
        """Arma las opciones de una ronda: lista de listas de lugares."""
        filtros, tipos = combinar_respuestas(respuestas)
        opciones = armar_opciones(
            lambda excluir: elegir_lugares(
                lambda tipo, f: self._lugares.buscar(tipo_id=tipo, filtros=f, limite=15, aleatorio=True),
                self._roles, filtros, tipos, excluir),
            ya_usados,
        )
        if not opciones:
            raise GrupoPlanError(
                "No encontré lugares que cumplan los filtros de todos. "
                "Pueden cambiar sus respuestas (por ejemplo subir el tope de precio) y probar de nuevo."
            )
        return opciones

    def _guardar_opciones(self, cursor, encuesta_id, ronda, opciones):
        for orden, lugares in enumerate(opciones, start=1):
            total = sumar_rangos([rango_de_nivel(l.get("nivel_precio")) for l in lugares])
            cursor.execute(
                """
                INSERT INTO public."Grupo_Encuesta_Opcion"
                    ("Id_Encuesta", "Ronda", "Orden", "Nombre", "Precio_Min", "Precio_Max", "Lugares")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (encuesta_id, ronda, orden, " + ".join(l["nombre"] for l in lugares),
                 total[0] if total else None, total[1] if total else None,
                 Json([{"id": l["id"], "nombre": l["nombre"], "nivel_precio": l.get("nivel_precio")}
                       for l in lugares])),
            )

    # --- Votar las opciones ----------------------------------------------------

    def votar(self, group_id, encuesta_id, user_id, opcion_id):
        """Vota una opción (id) o "ninguna" (None). Si con este voto ya votaron
        todos, se resuelve. Devuelve el resultado de la elección o None."""
        return self._votar_o_cerrar(group_id, encuesta_id, user_id, opcion_id=opcion_id)

    def _votar_o_cerrar(self, group_id, encuesta_id, user_id, opcion_id=None, cerrar=False):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                datos = self._datos(cursor, encuesta_id, group_id, user_id, ("eligiendo",))
                if cerrar:
                    if str(datos["creado_por"]) != str(user_id):
                        raise GrupoPlanError("Solo quien creó la encuesta puede cerrarla.")
                else:
                    if opcion_id is not None:
                        cursor.execute(
                            """
                            SELECT 1 FROM public."Grupo_Encuesta_Opcion"
                            WHERE "Id_Opcion" = %s AND "Id_Encuesta" = %s AND "Ronda" = %s
                            """,
                            (opcion_id, encuesta_id, datos["ronda"]),
                        )
                        if cursor.fetchone() is None:
                            raise GrupoPlanError("Esa opción ya no está disponible.")
                    cursor.execute(
                        """
                        INSERT INTO public."Grupo_Encuesta_Voto" ("Id_Encuesta", "Id_Usuario", "Ronda", "Id_Opcion")
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT ("Id_Encuesta", "Id_Usuario", "Ronda")
                        DO UPDATE SET "Id_Opcion" = EXCLUDED."Id_Opcion"
                        """,
                        (encuesta_id, user_id, datos["ronda"], opcion_id),
                    )
                resultado = self._resolver_eleccion(cursor, encuesta_id, group_id, datos, forzar=cerrar)
            connection.commit()
            return resultado
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    def _resolver_eleccion(self, cursor, encuesta_id, group_id, datos, forzar):
        """Cuenta los votos de la ronda actual. Devuelve 'plan_creado',
        'otros_planes', 'desempate' o None (todavía no se resuelve)."""
        ronda = datos["ronda"]
        cursor.execute(
            """
            SELECT o."Id_Opcion", COUNT(v."Id_Usuario")
            FROM public."Grupo_Encuesta_Opcion" o
            LEFT JOIN public."Grupo_Encuesta_Voto" v
                   ON v."Id_Opcion" = o."Id_Opcion" AND v."Ronda" = o."Ronda"
            WHERE o."Id_Encuesta" = %s AND o."Ronda" = %s
            GROUP BY o."Id_Opcion", o."Orden"
            ORDER BY o."Orden"
            """,
            (encuesta_id, ronda),
        )
        conteos = [(f[0], f[1]) for f in cursor.fetchall()]
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE "Id_Opcion" IS NULL), COUNT(*)
            FROM public."Grupo_Encuesta_Voto" WHERE "Id_Encuesta" = %s AND "Ronda" = %s
            """,
            (encuesta_id, ronda),
        )
        ninguna, total = cursor.fetchone()
        miembros = self._miembros(cursor, group_id)

        if total == 0:
            if forzar:
                raise GrupoPlanError("Todavía nadie votó: no se puede cerrar la elección.")
            return None
        if total < miembros and not forzar:
            return None

        mejor = max((n for _, n in conteos), default=0)
        if ninguna > mejor:
            return self._nueva_ronda(cursor, encuesta_id)

        empatadas = [i for i, n in conteos if n == mejor]
        if len(empatadas) > 1:
            if not datos["desempate"]:
                return self._desempate(cursor, encuesta_id, ronda, random.sample(empatadas, min(2, len(empatadas))))
            return self._crear_plan_ganador(cursor, encuesta_id, group_id, datos, random.choice(empatadas))
        return self._crear_plan_ganador(cursor, encuesta_id, group_id, datos, empatadas[0])

    def _nueva_ronda(self, cursor, encuesta_id):
        """Ganó "ninguna me convence": otros planes, sin repetir lugares."""
        cursor.execute(
            'SELECT "Lugares" FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Encuesta" = %s',
            (encuesta_id,),
        )
        usados = {frozenset(l["id"] for l in fila[0]) for fila in cursor.fetchall()}
        opciones = self._generar(self._respuestas(cursor, encuesta_id), usados)

        cursor.execute(
            'SELECT COALESCE(MAX("Ronda"), 0) + 1 FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Encuesta" = %s',
            (encuesta_id,),
        )
        ronda = cursor.fetchone()[0]
        self._guardar_opciones(cursor, encuesta_id, ronda, opciones)
        cursor.execute(
            'UPDATE public."Grupo_Encuesta" SET "Ronda" = %s, "Es_Desempate" = false WHERE "Id_Encuesta" = %s',
            (ronda, encuesta_id),
        )
        return "otros_planes"

    def _desempate(self, cursor, encuesta_id, ronda, finalistas):
        """Empate: se vota otra vez, solo entre las más votadas."""
        cursor.execute(
            'SELECT COALESCE(MAX("Ronda"), 0) + 1 FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Encuesta" = %s',
            (encuesta_id,),
        )
        nueva = cursor.fetchone()[0]
        for orden, opcion_id in enumerate(finalistas, start=1):
            cursor.execute(
                """
                INSERT INTO public."Grupo_Encuesta_Opcion"
                    ("Id_Encuesta", "Ronda", "Orden", "Nombre", "Precio_Min", "Precio_Max", "Lugares")
                SELECT "Id_Encuesta", %s, %s, "Nombre", "Precio_Min", "Precio_Max", "Lugares"
                FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Opcion" = %s
                """,
                (nueva, orden, opcion_id),
            )
        cursor.execute(
            'UPDATE public."Grupo_Encuesta" SET "Ronda" = %s, "Es_Desempate" = true WHERE "Id_Encuesta" = %s',
            (nueva, encuesta_id),
        )
        return "desempate"

    def _crear_plan_ganador(self, cursor, encuesta_id, group_id, datos, opcion_id):
        """Crea el plan en votación con la opción ganadora. Los que la votaron
        quedan con "me gusta" y con "puedo" según su disponibilidad, así el
        plan ya tiene votos y se puede cerrar."""
        cursor.execute(
            'SELECT "Nombre", "Lugares" FROM public."Grupo_Encuesta_Opcion" WHERE "Id_Opcion" = %s',
            (opcion_id,),
        )
        nombre_opcion, lugares = cursor.fetchone()
        fecha, hora = datos["fecha"], datos["hora"]

        plan_id = self._crear_plan(
            cursor, group_id, datos["creado_por"], fecha, hora, datos["titulo"], lugares,
            "Elegido por el grupo: " + nombre_opcion + ".")

        cursor.execute(
            """
            SELECT "Id_Usuario" FROM public."Grupo_Encuesta_Voto"
            WHERE "Id_Encuesta" = %s AND "Ronda" = %s AND "Id_Opcion" = %s
            """,
            (encuesta_id, datos["ronda"], opcion_id),
        )
        votantes = [str(f[0]) for f in cursor.fetchall()]
        disponibilidades = self._disponibilidades(cursor, encuesta_id)
        for uid in votantes:
            puede = any(
                d["user"] == uid and d["fecha"] == fecha and d["desde"] <= hora < d["hasta"]
                for d in disponibilidades
            )
            cursor.execute(
                'INSERT INTO public."Plan_Voto" ("Id_Plan", "Id_Usuario", "Me_Gusta", "Puedo") VALUES (%s, %s, true, %s)',
                (plan_id, uid, puede),
            )
        self._plan_grupo._resolver_votacion(cursor, plan_id)

        cursor.execute(
            'UPDATE public."Grupo_Encuesta" SET "Estado" = \'cerrada\', "Id_Plan" = %s WHERE "Id_Encuesta" = %s',
            (plan_id, encuesta_id),
        )
        return "plan_creado"

    def _crear_plan(self, cursor, group_id, creado_por, fecha, hora, nombre, lugares, descripcion):
        rangos = [rango_de_nivel(l.get("nivel_precio")) for l in lugares]
        total = sumar_rangos(rangos)

        # Lugar_id va en NULL explícito para no activar el DEFAULT de la columna
        # (ver PlanService.crear_idea).
        cursor.execute(
            """
            INSERT INTO public."Plan"
                ("Nombre", "Fecha", "Hora", "Descripcion", "Precio_Min", "Precio_Max",
                 "Creado_Por", "Estado", "Grupo_id", "Lugar_id")
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'votacion', %s, NULL)
            RETURNING "id_Plan"
            """,
            (nombre, fecha, hora, descripcion,
             total[0] if total else None, total[1] if total else None, creado_por, group_id),
        )
        plan_id = cursor.fetchone()[0]
        for orden, (lugar, rango) in enumerate(zip(lugares, rangos), start=1):
            cursor.execute(
                """
                INSERT INTO public."Plan_Lugar"
                    ("Id_Plan", "Id_Lugar", "Nombre", "Precio_Min", "Precio_Max", "Hora", "Orden")
                VALUES (%s, %s, %s, %s, %s, NULL, %s)
                """,
                (plan_id, lugar["id"], lugar["nombre"],
                 rango[0] if rango else None, rango[1] if rango else None, orden),
            )
        return plan_id

    # --- Lectura para la página del grupo -----------------------------------

    def get_abiertas(self, group_id, user_id):
        """Encuestas en curso del grupo (respondiendo o eligiendo), con lo
        que la página necesita para dibujar cada etapa."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT e."Id_Encuesta", e."Titulo", e."Fecha_Plan", e."Hora_Plan", e."Estado",
                           e."Ronda", e."Es_Desempate", e."Creado_Por", u."Nombre",
                           (SELECT COUNT(*) FROM public."Grupo_Encuesta_Respuesta" r
                             WHERE r."Id_Encuesta" = e."Id_Encuesta"),
                           (SELECT COUNT(*) FROM public."Usuario-Grupo" x WHERE x."Id_Grupo" = e."Id_Grupo"),
                           m."Nivel_Precio_Max", m."Apto_Menores", m."Opcion_Celiacos",
                           m."Opcion_Vegana", m."Tipos", (m."Id_Usuario" IS NOT NULL),
                           (SELECT COUNT(*) FROM public."Grupo_Encuesta_Voto" v
                             WHERE v."Id_Encuesta" = e."Id_Encuesta" AND v."Ronda" = e."Ronda")
                    FROM public."Grupo_Encuesta" e
                    LEFT JOIN public."Usuarios" u ON u."Id_Usuario" = e."Creado_Por"
                    LEFT JOIN public."Grupo_Encuesta_Respuesta" m
                           ON m."Id_Encuesta" = e."Id_Encuesta" AND m."Id_Usuario" = %s
                    WHERE e."Id_Grupo" = %s AND e."Estado" IN ('abierta', 'eligiendo')
                    ORDER BY e."Creada_En"
                    """,
                    (user_id, group_id),
                )
                encuestas = [
                    {
                        "id": str(f[0]), "titulo": f[1], "fecha": f[2], "hora": f[3], "estado": f[4],
                        "ronda": f[5], "desempate": f[6],
                        "es_creador": str(f[7]) == str(user_id), "creador": f[8],
                        "respondieron": f[9], "miembros": f[10],
                        "mi_nivel": f[11], "mi_menores": bool(f[12]), "mi_celiaco": bool(f[13]),
                        "mi_vegano": bool(f[14]), "mis_tipos": list(f[15] or []),
                        "yo_respondi": bool(f[16]), "votaron": f[17],
                        "franjas": [], "opciones": [], "mi_voto": None, "votos_ninguna": 0,
                    }
                    for f in cursor.fetchall()
                ]
                por_id = {e["id"]: e for e in encuestas}
                if not por_id:
                    return []

                # Mis franjas, para precargar el formulario.
                cursor.execute(
                    """
                    SELECT "Id_Encuesta", "Fecha", "Desde", "Hasta"
                    FROM public."Grupo_Encuesta_Disponibilidad"
                    WHERE "Id_Usuario" = %s AND "Id_Encuesta"::text = ANY(%s)
                    ORDER BY "Fecha", "Desde"
                    """,
                    (user_id, list(por_id)),
                )
                for f in cursor.fetchall():
                    por_id[str(f[0])]["franjas"].append({"fecha": f[1], "desde": f[2], "hasta": f[3]})

                # Opciones de la ronda actual con sus votos.
                cursor.execute(
                    """
                    SELECT o."Id_Encuesta", o."Id_Opcion", o."Nombre", o."Precio_Min", o."Precio_Max",
                           o."Lugares", COUNT(v."Id_Usuario"),
                           COALESCE(BOOL_OR(v."Id_Usuario" = %(uid)s), false)
                    FROM public."Grupo_Encuesta_Opcion" o
                    JOIN public."Grupo_Encuesta" e ON e."Id_Encuesta" = o."Id_Encuesta" AND e."Ronda" = o."Ronda"
                    LEFT JOIN public."Grupo_Encuesta_Voto" v
                           ON v."Id_Opcion" = o."Id_Opcion" AND v."Ronda" = o."Ronda"
                    WHERE o."Id_Encuesta"::text = ANY(%(ids)s) AND e."Estado" = 'eligiendo'
                    GROUP BY o."Id_Encuesta", o."Id_Opcion", o."Orden"
                    ORDER BY o."Orden"
                    """,
                    {"uid": user_id, "ids": list(por_id)},
                )
                for f in cursor.fetchall():
                    encuesta = por_id[str(f[0])]
                    encuesta["opciones"].append({
                        "id": str(f[1]), "nombre": f[2], "precio_min": f[3], "precio_max": f[4],
                        "lugares": [l["nombre"] for l in f[5]], "votos": f[6], "mio": bool(f[7]),
                    })
                    if f[7]:
                        encuesta["mi_voto"] = str(f[1])

                # Votos de "ninguna" y si yo voté "ninguna".
                cursor.execute(
                    """
                    SELECT v."Id_Encuesta", COUNT(*), COALESCE(BOOL_OR(v."Id_Usuario" = %s), false)
                    FROM public."Grupo_Encuesta_Voto" v
                    JOIN public."Grupo_Encuesta" e ON e."Id_Encuesta" = v."Id_Encuesta" AND e."Ronda" = v."Ronda"
                    WHERE v."Id_Opcion" IS NULL AND v."Id_Encuesta"::text = ANY(%s)
                    GROUP BY v."Id_Encuesta"
                    """,
                    (user_id, list(por_id)),
                )
                for f in cursor.fetchall():
                    encuesta = por_id[str(f[0])]
                    encuesta["votos_ninguna"] = f[1]
                    if f[2]:
                        encuesta["mi_voto"] = "ninguna"
            return encuestas
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)