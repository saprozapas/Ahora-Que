"""Datos legales de Premium: quién vende, qué versión de las condiciones rige y si la demo está encendida.

Todo lo que cambia cuando Premium deje de ser una maqueta vive ACÁ, en un solo lugar, y las plantillas
lo leen desde acá (ver routes/suscripcion.py, que lo inyecta en todas las plantillas).
"""
import os

from services.seguridad import en_produccion

# Versión y fecha de los textos legales. Se muestran en terminos.html y privacidad.html y se guardan junto a la
# aceptación de cada persona al registrarse (Aceptaciones_Legales). Subilas cada vez que cambie el texto.
VERSION_TERMINOS = "1.2"
FECHA_TERMINOS = "3 de noviembre de 2026"
VERSION_PRIVACIDAD = "1.2"
FECHA_PRIVACIDAD = "5 de noviembre de 2026"

# Cambiala cada vez que se modifiquen las condiciones de Premium en terminos.html.
# Se guarda en Premium_Historial junto a cada alta: así se puede probar a qué condiciones aceptó cada persona.
VERSION_CONDICIONES_PREMIUM = "2026-11-03"

# Premium es solo para mayores de edad: un menor no puede contratar por su cuenta.
EDAD_MINIMA_PREMIUM = 18

# Quién vende. Mientras no exista un titular real quedan los textos entre corchetes, bien visibles.
# Cuando lo haya, se cargan como variables de entorno (en Render) y no hace falta tocar el código.
PROVEEDOR = {
    "razon_social": os.environ.get("PROVEEDOR_RAZON_SOCIAL", "[Razón social del titular: completar]"),
    "rut": os.environ.get("PROVEEDOR_RUT", "[RUT: completar]"),
    "domicilio": os.environ.get("PROVEEDOR_DOMICILIO", "[Domicilio en Uruguay: completar]"),
    "email": os.environ.get("PROVEEDOR_EMAIL", "ahora.que.app@gmail.com"),
    # Inscripción de la base de datos en el Registro de Bases de Datos Personales de la URCDP (Ley 18.331, art. 6).
    "urcdp": os.environ.get("PROVEEDOR_URCDP", "[N.º de inscripción: completar]"),
}


def es_menor(fecha_nac, hoy=None):
    """True si la persona tiene menos de 18 años (los menores tienen perfiles y publicaciones más protegidos)."""
    from datetime import date
    hoy = hoy or date.today()
    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    return edad < EDAD_MINIMA_PREMIUM


def premium_demo_activo():
    """True si la demostración de pago está encendida.

    - En tu computadora (no producción) siempre está encendida.
    - En producción (Render) solo si definís PREMIUM_DEMO=1. Sin esa variable, /premium/pagar no
      activa nada: así nadie se vuelve Premium gratis en un despliegue público por accidente.
    """
    if os.environ.get("PREMIUM_DEMO") == "1":
        return True
    return not en_produccion()
