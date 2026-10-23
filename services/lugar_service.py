import psycopg2

from database import get_db_connection, release_db_connection
from services.lugar_filtros import construir_condiciones, quitar_tildes


# Minúsculas y sin tildes del lado de SQL (no depende de la extensión unaccent).
_SIN_TILDES = "translate(lower({col}), 'áéíóúüñ', 'aeiouun')"


# Distancia en km entre el punto (lat, lon) del usuario y el lugar, en línea recta sobre la esfera
# (haversine). Los tres %s son: latitud del usuario, latitud del usuario y longitud del usuario.
_HAVERSINE_KM = (
    '2 * 6371 * asin(sqrt('
    'power(sin(radians(l."Lat"::float8 - %s) / 2), 2) + '
    'cos(radians(%s)) * cos(radians(l."Lat"::float8)) * '
    'power(sin(radians(l."Long"::float8 - %s) / 2), 2)'
    '))'
)


def url_mapa(lat, lon):
    """Enlace a un mapa (Google Maps abre la app o el navegador en cualquier teléfono) con el punto exacto
    del lugar. None si el lugar no tiene coordenadas."""
    try:
        return f"https://www.google.com/maps/search/?api=1&query={float(lat):.6f},{float(lon):.6f}"
    except (TypeError, ValueError):
        return None


def _coordenadas_validas(lat, lon):
    """(lat, lon) como floats si son una ubicación posible; si no, None."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


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

    def buscar_barrios(self, texto="", limite=8):
        """Barrios que coinciden con lo escrito, con cuántos lugares tiene cada uno.

        Sin tildes ni mayúsculas ("poci" encuentra "Pocitos"). Primero los que
        EMPIEZAN con el texto, después los que lo contienen; dentro de cada grupo,
        el que más lugares tiene.
        """
        texto = quitar_tildes((texto or "").strip())
        limite = max(1, min(int(limite), 20))
        col = _SIN_TILDES.format(col='l."Barrio"')

        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT l."Barrio", COUNT(*) AS lugares
                    FROM public."Lugar" l
                    WHERE l."Barrio" IS NOT NULL AND l."Barrio" <> ''
                      AND {col} LIKE %s
                    GROUP BY l."Barrio"
                    ORDER BY CASE WHEN {col} LIKE %s THEN 0 ELSE 1 END, lugares DESC, l."Barrio"
                    LIMIT %s
                    """,
                    (f"%{texto}%", f"{texto}%", limite),
                )
                return [{"nombre": fila[0], "lugares": fila[1]} for fila in cursor.fetchall()]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def detalles(self, ids):
        """{id: {"direccion", "barrio", "mapa_url"}} de los lugares con esos ids (una sola consulta)."""
        ids = [str(i) for i in ids if i]
        if not ids:
            return {}
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT l."Id_Lugar"::text, l."Direccion", l."Barrio", l."Lat"::float8, l."Long"::float8
                    FROM public."Lugar" l WHERE l."Id_Lugar"::text = ANY(%s)
                    """,
                    (ids,),
                )
                return {
                    f[0]: {"direccion": f[1], "barrio": f[2], "mapa_url": url_mapa(f[3], f[4])}
                    for f in cursor.fetchall()
                }
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def barrio_canonico(self, texto):
        """El barrio de la base que coincide con lo escrito (sin tildes ni mayúsculas), o None."""
        texto = quitar_tildes((texto or "").strip())
        if not texto:
            return None
        col = _SIN_TILDES.format(col='l."Barrio"')
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT l."Barrio" FROM public."Lugar" l WHERE {col} = %s LIMIT 1',
                    (texto,),
                )
                fila = cursor.fetchone()
                return fila[0] if fila else None
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def centros_de_barrios(self, barrios):
        """{barrio: (lat, lon)}: el centro de cada barrio es el promedio de sus lugares."""
        barrios = [b for b in set(barrios or []) if b]
        if not barrios:
            return {}
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT l."Barrio", AVG(l."Lat"::float8), AVG(l."Long"::float8)
                    FROM public."Lugar" l
                    WHERE l."Barrio" = ANY(%s) AND l."Lat" IS NOT NULL AND l."Long" IS NOT NULL
                    GROUP BY l."Barrio"
                    """,
                    (barrios,),
                )
                return {f[0]: (f[1], f[2]) for f in cursor.fetchall()}
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def barrio_cercano(self, lat, lon):
        """El barrio del lugar más cercano a (lat, lon), o None si no hay datos."""
        coordenadas = _coordenadas_validas(lat, lon)
        if not coordenadas:
            return None
        connection = get_db_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT l."Barrio"
                    FROM public."Lugar" l
                    WHERE l."Barrio" IS NOT NULL AND l."Barrio" <> ''
                      AND l."Lat" IS NOT NULL AND l."Long" IS NOT NULL
                    ORDER BY {_HAVERSINE_KM}
                    LIMIT 1
                    """,
                    (coordenadas[0], coordenadas[0], coordenadas[1]),
                )
                fila = cursor.fetchone()
                return fila[0] if fila else None
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)

    def buscar(self, texto="", tipo_id="", filtros=None, limite=30, aleatorio=False,
               lat=None, lon=None, max_km=None, barrios=None, cerca_de=None):
        """Busca lugares por nombre o por tipo, aplicando los filtros.

        barrios: lista de nombres; solo lugares de alguno de ellos.
        cerca_de: lista de (lat, lon, km); el lugar tiene que quedar a menos de km de CADA punto.

        Si llegan lat y lon (la ubicación de quien busca), cada lugar trae su
        distancia en km (fórmula de haversine, sin PostGIS) y los resultados van
        del más cercano al más lejano; max_km descarta los que quedan más lejos.

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

        if barrios:
            condiciones.append(f'{_SIN_TILDES.format(col="l.\"Barrio\"")} = ANY(%s)')
            parametros.append([quitar_tildes(b) for b in barrios])

        for lat_c, lon_c, km in cerca_de or []:
            condiciones.append(f"{_HAVERSINE_KM} <= %s")
            parametros.extend([lat_c, lat_c, lon_c, km])

        where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

        # Distancia al usuario: solo si mandó una ubicación válida.
        coordenadas = _coordenadas_validas(lat, lon)
        if coordenadas:
            columna_distancia = f'{_HAVERSINE_KM} AS distancia_km'
            # Mismo orden que los %s de _HAVERSINE_KM: latitud, latitud y longitud.
            parametros_distancia = [coordenadas[0], coordenadas[0], coordenadas[1]]
        else:
            columna_distancia = 'NULL::float8 AS distancia_km'
            parametros_distancia = []

        filtro_distancia, parametros_max = "", []
        if coordenadas and max_km not in (None, ""):
            try:
                tope = float(max_km)
            except (TypeError, ValueError):
                tope = None
            if tope is not None and 0 < tope <= 500:
                filtro_distancia, parametros_max = "WHERE u.distancia_km <= %s", [tope]

        if aleatorio:
            orden, parametros_orden = "random()", []
        elif coordenadas:
            orden, parametros_orden = 'u.distancia_km, u."Nombre"', []
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
                   u."Barrio", u."Precio_Origen", u.tipos, u.distancia_km
            FROM (
                SELECT DISTINCT
                    l."Id_Lugar", l."Nombre", l."Direccion",
                    l."Nivel_Precio", l."Ambiente", l."Barrio", l."Precio_Origen",
                    {columna_distancia},
                    (SELECT string_agg(tt."Nombre", ', ' ORDER BY tt."Nombre")
                       FROM public."Lugar_Tipo" x
                       JOIN public."Tipo" tt ON tt."Id_Tipo" = x."Tipo_id"
                      WHERE x."Lugar_id" = l."Id_Lugar") AS tipos
                FROM public."Lugar" l
                LEFT JOIN public."Lugar_Tipo" lt ON lt."Lugar_id" = l."Id_Lugar"
                LEFT JOIN public."Tipo" t ON t."Id_Tipo" = lt."Tipo_id"
                {where}
            ) u
            {filtro_distancia}
            ORDER BY {orden}
            LIMIT %s
        """
        # El orden de los %s sigue el del texto de la consulta: primero la distancia
        # (lista de columnas), después el WHERE de adentro, el tope de km, el ORDER BY y el LIMIT.
        parametros = parametros_distancia + parametros + parametros_max + parametros_orden
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
                        "distancia_km": round(fila[8], 2) if fila[8] is not None else None,
                    }
                    for fila in cursor.fetchall()
                ]
        except psycopg2.Error:
            raise
        finally:
            release_db_connection(connection)
