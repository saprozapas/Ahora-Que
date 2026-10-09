import psycopg2

from database import get_db_connection, release_db_connection
from services.lugar_filtros import construir_condiciones


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

        aleatorio=True mezcla los resultados en vez de ordenarlos por
        nombre (lo usa el chatbot, para que no proponga siempre los
        primeros lugares del abecedario).
        """
        condiciones = []
        parametros = []

        texto = (texto or "").strip()
        if texto:
            # El texto busca tanto en el nombre del lugar como en el del tipo.
            condiciones.append('(l."Nombre" ILIKE %s OR t."Nombre" ILIKE %s)')
            parametros.extend([f"%{texto}%", f"%{texto}%"])

        tipo_id = (tipo_id or "").strip()
        if tipo_id:
            condiciones.append('t."Id_Tipo"::text = %s')
            parametros.append(tipo_id)

        condiciones_filtros, parametros_filtros = construir_condiciones(filtros or {})
        condiciones.extend(condiciones_filtros)
        parametros.extend(parametros_filtros)

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        orden = "random()" if aleatorio else 'u."Nombre"'
        # Subconsulta: SELECT DISTINCT no permite ORDER BY random().
        consulta = f"""
            SELECT u."Id_Lugar", u."Nombre", u."Direccion", u."Nivel_Precio", u."Ambiente"
            FROM (
                SELECT DISTINCT
                    l."Id_Lugar", l."Nombre", l."Direccion",
                    l."Nivel_Precio", l."Ambiente"
                FROM public."Lugar" l
                LEFT JOIN public."Lugar_Tipo" lt ON lt."Lugar_id" = l."Id_Lugar"
                LEFT JOIN public."Tipo" t ON t."Id_Tipo" = lt."Tipo_id"
                {where}
            ) u
            ORDER BY {orden}
            LIMIT %s
        """
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
                    }
                    for fila in cursor.fetchall()
                ]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)