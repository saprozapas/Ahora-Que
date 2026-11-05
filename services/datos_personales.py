"""Derecho de acceso (Ley 18.331, art. 14): todo lo que la app guarda de una persona, en un archivo que puede bajar."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from database import get_db_connection, release_db_connection
from services.deuda_service import DeudaService


def _simple(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, (UUID, Decimal)):
        return str(valor)
    return valor


# (nombre en el archivo, consulta, nombres de las columnas). Cada consulta recibe el id de la persona.
_BLOQUES = (
    ("grupos", 'SELECT g."Nombre", ug."Es_Admin" FROM public."Usuario-Grupo" ug JOIN public."Grupos" g ON g."Id_Grupo" = ug."Id_Grupo" WHERE ug."Id_Usuario" = %s ORDER BY g."Nombre"', ("grupo", "es_admin")),
    ("planes", 'SELECT p."Nombre", p."Fecha", up."Confirmado", up."Guardado", up."Puntaje" FROM public."Usuario-Plan" up JOIN public."Plan" p ON p."id_Plan" = up."Plan_id" WHERE up."Usuario_id" = %s ORDER BY p."Fecha" DESC NULLS LAST', ("plan", "fecha", "confirmado", "guardado", "puntaje")),
    ("mensajes_de_chat_de_grupo", 'SELECT "Contenido", "Fecha_Envio" FROM public."Mensajes" WHERE "Id_Usuario" = %s ORDER BY "Fecha_Envio"', ("mensaje", "fecha")),
    ("publicaciones", 'SELECT "Texto", "Visibilidad", "Creada_En" FROM public."Publicacion" WHERE "Id_Autor" = %s AND NOT "Eliminada" ORDER BY "Creada_En"', ("texto", "visibilidad", "fecha")),
    ("comentarios", 'SELECT "Contenido", "Creado_En" FROM public."Publicacion_Comentario" WHERE "Id_Usuario" = %s AND NOT "Eliminado" ORDER BY "Creado_En"', ("comentario", "fecha")),
    ("amistades", 'SELECT u."Username" FROM public."Amistades" a JOIN public."Usuarios" u ON u."Id_Usuario" = CASE WHEN a."Id_Usuario1" = %(u)s THEN a."Id_Usuario2" ELSE a."Id_Usuario1" END WHERE %(u)s IN (a."Id_Usuario1", a."Id_Usuario2")', ("usuario",)),
    ("deudas", 'SELECT u."Username", d."Saldo", d."Id_Usuario1" = %(u)s FROM public."Deuda" d JOIN public."Usuarios" u ON u."Id_Usuario" = CASE WHEN d."Id_Usuario1" = %(u)s THEN d."Id_Usuario2" ELSE d."Id_Usuario1" END WHERE %(u)s IN (d."Id_Usuario1", d."Id_Usuario2")', ("con", "saldo", "esa_persona_es_el_primer_usuario_del_par")),
    ("aceptaciones_legales", 'SELECT "Version_Terminos", "Version_Privacidad", "Aceptado_En", "Tutor_Declarado" FROM public."Aceptaciones_Legales" WHERE "Id_Usuario" = %s ORDER BY "Aceptado_En"', ("version_terminos", "version_privacidad", "aceptado_en", "tutor_declarado")),
    ("historial_de_premium", 'SELECT "Accion", "Ciclo", "Version_Condiciones", "Creado_En" FROM public."Premium_Historial" WHERE "Id_Usuario" = %s ORDER BY "Creado_En"', ("accion", "ciclo", "version_condiciones", "fecha")),
)


def exportar(user_id):
    """Todo lo que se guarda de la persona (sin su contraseña ni datos de otras personas). Cada bloque se lee por separado:
    si uno falla, el resto igual sale y el bloque que falló queda marcado."""
    datos = {"generado_el": datetime.now(timezone.utc).isoformat(timespec="seconds"), "id": str(user_id)}
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT "Nombre", "Username", "Mail", "Fecha_Nac", "Descripcion" FROM public."Usuarios" WHERE "Id_Usuario" = %s', (user_id,))
            fila = cur.fetchone()
            datos["cuenta"] = dict(zip(("nombre", "usuario", "correo", "fecha_de_nacimiento", "descripcion"), map(_simple, fila))) if fila else {}
        for nombre, consulta, columnas in _BLOQUES:
            try:
                with conn.cursor() as cur:
                    cur.execute(consulta, {"u": str(user_id)} if "%(u)s" in consulta else (str(user_id),))
                    datos[nombre] = [dict(zip(columnas, map(_simple, f))) for f in cur.fetchall()]
            except Exception as e:
                conn.rollback()
                print(f"No se pudo exportar {nombre}: {e}")
                datos[nombre] = "no disponible"
    finally:
        release_db_connection(conn)
    cuenta = DeudaService().get_cuenta(user_id)
    datos["cuenta_bancaria"] = {"banco": cuenta["banco"], "numero": cuenta["cuenta"]} if cuenta["banco"] else None
    datos["nota"] = "No incluye tu contraseña (solo guardamos un hash) ni datos de otras personas. Para cualquier otro dato escribinos a ahora.que.app@gmail.com."
    return datos
