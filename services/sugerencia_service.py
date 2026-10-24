"""Los 3 planes que el asistente le sugiere a cada usuario por semana (Inicio, "Para vos esta semana").

Se arman una vez por usuario y por semana (el lunes empieza una nueva) y se guardan en
"Sugerencia_Semanal": abrir el Inicio no vuelve a llamar al modelo.

Qué mira el asistente:
  - la descripción del perfil,
  - los lugares de sus planes (guardados o confirmados), los mejor puntuados primero,
  - sus tipos de lugar y barrios más frecuentes y el precio al que está acostumbrado.
Con eso se arma una lista de lugares candidatos (mezclada distinto cada semana, sin repetir lo que ya
visitó) y el modelo la combina en 3 planes. Si el modelo no responde o devuelve algo inválido, los planes
se arman igual con los candidatos, sin descripción personalizada.
"""

import json
import re
import threading
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import psycopg2
from psycopg2.extras import Json

import ia_bridge
from database import get_db_connection, release_db_connection
from services import llm_service
from services.plan_service import PlanService

CANTIDAD = 3
# Uruguay no tiene horario de verano: siempre UTC-3.
_HUSO = timezone(timedelta(hours=-3))
_candados = {}
_candados_lock = threading.Lock()


def lunes_de_esta_semana():
    hoy = datetime.now(_HUSO).date()
    return hoy - timedelta(days=hoy.weekday())


def _candado(user_id):
    with _candados_lock:
        return _candados.setdefault(str(user_id), threading.Lock())


class SugerenciaService:

    def __init__(self):
        self._planes = PlanService()

    # --- Lectura ----------------------------------------------------------------

    def existentes(self, user_id, semana=None):
        """Las sugerencias ya guardadas de esta semana ([] si todavía no se armaron)."""
        semana = semana or lunes_de_esta_semana()
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT "Id_Sugerencia", "Nombre", "Descripcion", "Lugares"
                    FROM public."Sugerencia_Semanal"
                    WHERE "Id_Usuario" = %s AND "Semana" = %s
                    ORDER BY "Orden"
                    """,
                    (user_id, semana),
                )
                return [self._armar(fila) for fila in cursor.fetchall()]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    @staticmethod
    def _armar(fila):
        lugares = fila[3] if isinstance(fila[3], list) else json.loads(fila[3] or "[]")
        con_mapa = [l for l in lugares if l.get("lat") and l.get("lon")]
        return {
            "id": str(fila[0]),
            "nombre": fila[1],
            "descripcion": fila[2],
            "lugares": lugares,
            "resumen": " → ".join(l["nombre"] for l in lugares),
            "lat": con_mapa[0]["lat"] if con_mapa else None,
            "lon": con_mapa[0]["lon"] if con_mapa else None,
        }

    def obtener(self, user_id):
        """Las de esta semana; si todavía no existen, se arman ahora (puede tardar unos segundos)."""
        semana = lunes_de_esta_semana()
        existentes = self.existentes(user_id, semana)
        if existentes:
            return existentes
        with _candado(user_id):  # dos pedidos a la vez no llaman dos veces al modelo
            existentes = self.existentes(user_id, semana)
            if existentes:
                return existentes
            self._generar(user_id, semana)
        return self.existentes(user_id, semana)

    # --- Armado -----------------------------------------------------------------

    def _perfil_y_gustos(self, cursor, user_id):
        cursor.execute('SELECT "Descripcion" FROM public."Usuarios" WHERE "Id_Usuario" = %s', (user_id,))
        fila = cursor.fetchone()
        descripcion = (fila[0] or "").strip() if fila else ""

        cursor.execute(
            """
            SELECT l."Id_Lugar"::text, l."Nombre", l."Barrio", l."Nivel_Precio", up."Puntaje"
            FROM public."Usuario-Plan" up
            JOIN public."Plan_Lugar" pl ON pl."Id_Plan" = up."Plan_id"
            JOIN public."Lugar" l ON l."Id_Lugar" = pl."Id_Lugar"
            WHERE up."Usuario_id" = %s AND (up."Confirmado" OR up."Guardado")
            ORDER BY up."Puntaje" DESC NULLS LAST
            LIMIT 60
            """,
            (user_id,),
        )
        historial = cursor.fetchall()
        return descripcion, historial

    def _candidatos(self, cursor, barrios, nivel_max, visitados, semilla):
        """Lugares con ubicación, sin repetir lo ya visitado; distinto orden cada semana."""
        base = """
            SELECT l."Id_Lugar"::text, l."Nombre", l."Barrio", l."Nivel_Precio", l."Lat"::float8, l."Long"::float8
            FROM public."Lugar" l
            WHERE l."Lat" IS NOT NULL AND l."Long" IS NOT NULL AND l."Nombre" IS NOT NULL
              AND l."Id_Lugar"::text <> ALL(%(visitados)s)
              AND (%(nivel)s IS NULL OR l."Nivel_Precio" IS NULL OR l."Nivel_Precio" <= %(nivel)s)
        """
        parametros = {"visitados": visitados or [""], "nivel": nivel_max, "semilla": semilla}
        candidatos = {}
        if barrios:
            cursor.execute(
                base + ' AND l."Barrio" = ANY(%(barrios)s) ORDER BY md5(l."Id_Lugar"::text || %(semilla)s) LIMIT 22',
                {**parametros, "barrios": barrios},
            )
            for fila in cursor.fetchall():
                candidatos[fila[0]] = fila
        cursor.execute(base + ' ORDER BY md5(l."Id_Lugar"::text || %(semilla)s) LIMIT 40', parametros)
        for fila in cursor.fetchall():
            if len(candidatos) >= 40:
                break
            candidatos.setdefault(fila[0], fila)
        return list(candidatos.values())

    def _generar(self, user_id, semana):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                descripcion, historial = self._perfil_y_gustos(cursor, user_id)
                visitados = [h[0] for h in historial]
                barrios = [b for b, _ in Counter(h[2] for h in historial if h[2]).most_common(3)]
                niveles = [h[3] for h in historial if h[3] is not None]
                nivel_max = min(4, round(sum(niveles) / len(niveles)) + 1) if niveles else None
                candidatos = self._candidatos(cursor, barrios, nivel_max, visitados, f"{user_id}{semana}")
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

        if not candidatos:
            return

        tipos = ia_bridge.tipos_por_lugar([c[0] for c in candidatos] + visitados[:20])
        favoritos = [t for t, _ in Counter(t for v in visitados for t in tipos.get(v, [])).most_common(4)]

        planes = self._pedir_al_modelo(descripcion, historial, favoritos, barrios, candidatos, tipos)
        planes = self._completar(planes, candidatos, tipos)
        self._guardar(user_id, semana, planes[:CANTIDAD])

    def _pedir_al_modelo(self, descripcion, historial, favoritos, barrios, candidatos, tipos):
        lista = "\n".join(
            f"{c[0]} | {c[1]} | {c[2] or 'sin barrio'} | {', '.join(tipos.get(c[0], [])) or 'sin tipo'} | precio {c[3] if c[3] is not None else '?'}"
            for c in candidatos
        )
        mejores = [f"{h[1]} ({h[4]}★)" for h in historial if h[4] is not None and h[4] >= 4][:6]
        contexto = [
            f"Descripción de su perfil: {descripcion or 'no escribió ninguna'}",
            f"Tipos de lugar que más usa: {', '.join(favoritos) or 'todavía no se sabe'}",
            f"Barrios que más frecuenta: {', '.join(barrios) or 'todavía no se sabe'}",
            f"Lugares que puntuó alto: {', '.join(mejores) or 'ninguno todavía'}",
        ]
        mensajes = [
            {"role": "system", "content": (
                "Sos el asistente de Ahora Qué, una app para planear salidas en Montevideo. "
                f"Armá exactamente {CANTIDAD} planes distintos entre sí para esta persona, usando SOLO lugares de la lista (por su id). "
                "Cada plan combina 1 a 3 lugares que tengan sentido juntos, cerca entre sí (por ejemplo un café y un paseo; "
                "nunca dos lugares para comer en el mismo plan). Escribí en español rioplatense, tuteando con voseo. "
                "'nombre': corto y atractivo, máximo 4 palabras, sin emojis ni comillas. "
                "'descripcion': una sola frase, máximo 110 caracteres, que diga por qué le puede gustar a esta persona. "
                'Respondé SOLO con JSON válido: {"planes":[{"nombre":"...","descripcion":"...","lugares":["id","id"]}]}'
            )},
            {"role": "user", "content": "\n".join(contexto) + "\n\nLugares disponibles (id | nombre | barrio | tipos | precio 0-4):\n" + lista},
        ]
        try:
            respuesta = llm_service.chat_completion(mensajes, temperature=0.7)
            texto = (respuesta.content or "").strip()
            texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
            inicio, fin = texto.find("{"), texto.rfind("}")
            datos = json.loads(texto[inicio:fin + 1])
        except Exception as e:  # sin clave, sin red, JSON roto…: se arma sin modelo
            print(f"[sugerencias] el modelo no respondió bien: {e}", flush=True)
            return []

        por_id = {c[0]: c for c in candidatos}
        planes = []
        for plan in datos.get("planes", []) if isinstance(datos, dict) else []:
            ids = [i for i in dict.fromkeys(str(x) for x in plan.get("lugares", [])) if i in por_id][:3]
            nombre = str(plan.get("nombre") or "").strip()[:60]
            if ids and nombre:
                planes.append({
                    "nombre": nombre,
                    "descripcion": str(plan.get("descripcion") or "").strip()[:140] or None,
                    "ids": ids,
                })
        return planes

    def _completar(self, planes, candidatos, tipos):
        """Si el modelo trajo menos de 3 planes, se arman los que faltan con los candidatos que sobran."""
        usados = {i for p in planes for i in p["ids"]}
        libres = [c for c in candidatos if c[0] not in usados]
        while len(planes) < CANTIDAD and libres:
            grupo = libres[:2]
            libres = libres[2:]
            barrio = next((c[2] for c in grupo if c[2]), None)
            planes.append({
                "nombre": f"Salida por {barrio}" if barrio else "Salida de la semana",
                "descripcion": None,
                "ids": [c[0] for c in grupo],
            })
        por_id = {c[0]: c for c in candidatos}
        resultado = []
        for plan in planes:
            lugares = [
                {"id": por_id[i][0], "nombre": por_id[i][1], "barrio": por_id[i][2], "nivel_precio": por_id[i][3],
                 "lat": por_id[i][4], "lon": por_id[i][5], "tipos": tipos.get(i, [])}
                for i in plan["ids"]
            ]
            resultado.append({"nombre": plan["nombre"], "descripcion": plan["descripcion"], "lugares": lugares})
        return resultado

    def _guardar(self, user_id, semana, planes):
        if not planes:
            return
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                for orden, plan in enumerate(planes, start=1):
                    cursor.execute(
                        """
                        INSERT INTO public."Sugerencia_Semanal" ("Id_Usuario", "Semana", "Orden", "Nombre", "Descripcion", "Lugares")
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT ("Id_Usuario", "Semana", "Orden") DO NOTHING
                        """,
                        (user_id, semana, orden, plan["nombre"], plan["descripcion"], Json(plan["lugares"])),
                    )
                # Las semanas viejas no sirven para nada: se limpian de a poco.
                cursor.execute(
                    'DELETE FROM public."Sugerencia_Semanal" WHERE "Id_Usuario" = %s AND "Semana" < %s',
                    (user_id, semana - timedelta(days=14)),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            release_db_connection(connection)

    # --- Guardar una sugerencia como idea --------------------------------------

    def guardar_como_idea(self, user_id, sugerencia_id):
        """Copia la sugerencia a los planes del usuario como una idea. Devuelve el id de la idea o None."""
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT "Nombre", "Descripcion", "Lugares"
                    FROM public."Sugerencia_Semanal"
                    WHERE "Id_Sugerencia"::text = %s AND "Id_Usuario" = %s
                    """,
                    (str(sugerencia_id), user_id),
                )
                fila = cursor.fetchone()
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

        if fila is None:
            return None
        lugares = fila[2] if isinstance(fila[2], list) else json.loads(fila[2] or "[]")
        return self._planes.crear_idea(
            user_id, fila[0], fila[1] or "",
            [{"id_lugar": l["id"], "nombre": l["nombre"], "nivel_precio": l.get("nivel_precio"), "hora": None} for l in lugares],
        )
