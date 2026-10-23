import psycopg2

from database import get_db_connection, release_db_connection
from services.lugar_filtros import construir_condiciones, quitar_tildes


# Minúsculas y sin tildes del lado de SQL (no depende de la extensión unaccent).
_SIN_TILDES = "translate(lower({col}), 'áéíóúüñ', 'aeiouun')"


class LugarService:

    def listar_tipos(self):
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT "Id_Tipo", "Nombre"
                    FROM public."Tipo"
                    ORDER BY "Nombre"
                    """
                )
                return [
                    {"id": fila[0], "nombre": fila[1]}
                    for fila in cursor.fetchall()
                ]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def buscar(self, texto="", tipo_id="", filtros=None, limite=30, aleatorio=False):
        """Busca lugares por nombre o por tipo, aplicando los filtros.

        Los filtros salen de services/lugar_filtros.py: para agregar o
        sacar uno no hace falta tocar esta función.

        El texto no distingue mayúsculas ni tildes ("cafe" encuentra "Café").
        Cuando hay texto, primero van los lugares cuyo nombre EMPIEZA con eso y
        después los demás, por orden alfabético.

        aleatorio=True mezcla los resultados en vez de ordenarlos por
        nombre (lo usa el chatbot, para que no proponga siempre los
        primeros lugares del abecedario).
        """
        condiciones = []
        parametros = []

        texto = quitar_tildes((texto or "").strip())
        if texto:
            condiciones.append(
                f'({_SIN_TILDES.format(col="l.\"Nombre\"")} LIKE %s'
                f' OR {_SIN_TILDES.format(col="t.\"Nombre\"")} LIKE %s)'
            )
            parametros.extend([f"%{texto}%", f"%{texto}%"])

        tipo_id = (tipo_id or "").strip()
        if tipo_id:
            condiciones.append('t."Id_Tipo"::text = %s')
            parametros.append(tipo_id)

        condiciones_filtros, parametros_filtros = construir_condiciones(filtros or {})
        condiciones.extend(condiciones_filtros)
        parametros.extend(parametros_filtros)

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        if aleatorio:
            orden, parametros_orden = "random()", []
        elif texto:
            orden = (f'CASE WHEN {_SIN_TILDES.format(col="u.\"Nombre\"")} LIKE %s THEN 0 ELSE 1 END, '
                     'u."Nombre"')
            parametros_orden = [f"{texto}%"]
        else:
            orden, parametros_orden = 'u."Nombre"', []

        limite = max(1, min(int(limite), 60))

        # Subconsulta: SELECT DISTINCT no permite ORDER BY random().
        consulta = f"""
            SELECT u."Id_Lugar", u."Nombre", u."Direccion", u."Nivel_Precio", u."Ambiente",
                   u."Barrio", u."Precio_Origen", u.tipos
            FROM (
                SELECT DISTINCT
                    l."Id_Lugar", l."Nombre", l."Direccion",
                    l."Nivel_Precio", l."Ambiente", l."Barrio", l."Precio_Origen",
                    (SELECT string_agg(tt."Nombre", ', ' ORDER BY tt."Nombre")
                       FROM public."Lugar_Tipo" x
                       JOIN public."Tipo" tt ON tt."Id_Tipo" = x."Tipo_id"
                      WHERE x."Lugar_id" = l."Id_Lugar") AS tipos
                FROM public."Lugar" l
                LEFT JOIN public."Lugar_Tipo" lt ON lt."Lugar_id" = l."Id_Lugar"
                LEFT JOIN public."Tipo" t ON t."Id_Tipo" = lt."Tipo_id"
                {where}
            ) u
            ORDER BY {orden}
            LIMIT %s
        """
        parametros.extend(parametros_orden)
        parametros.append(limite)

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(consulta, parametros)
                return [
                    {
                        "id": str(fila[0]),
                        "nombre": fila[1],
                        "direccion": fila[2],
                        "nivel_precio": fila[3],
                        "ambiente": fila[4],
                        "barrio": fila[5],
                        "precio_origen": fila[6],
                        "tipos": fila[7] or "",
                    }
                    for fila in cursor.fetchall()
                ]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)
