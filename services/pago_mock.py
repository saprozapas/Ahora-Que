"""Validación de datos de pago de MENTIRA (maqueta).

No cobra ni se conecta a ningún banco: solo revisa que los datos tengan forma válida
(Luhn del número de tarjeta, vencimiento, CVV, cédula uruguaya, etc.).
Los datos NO se guardan ni se registran en ningún lado: se leen del formulario y se descartan.
Cada validar_* devuelve {campo: mensaje}; vacío = todo bien.
"""
import re
from datetime import date

BANCOS = ["BROU", "Itaú", "Santander", "BBVA", "Scotiabank", "HSBC", "Heritage"]
_NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]{2,}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _digitos(texto):
    return re.sub(r"\D", "", texto or "")


def luhn_ok(numero):
    suma = 0
    for i, d in enumerate(reversed(numero)):
        n = int(d)
        if i % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        suma += n
    return suma % 10 == 0


def ci_valida(texto):
    """Cédula uruguaya: 7 dígitos + dígito verificador (ej. 1.234.567-2)."""
    d = _digitos(texto)
    if not 7 <= len(d) <= 8:
        return False
    d = d.zfill(8)
    suma = sum(int(x) * int(p) for x, p in zip(d[:7], "2987634"))
    return int(d[7]) == (10 - suma % 10) % 10


def validar_tarjeta(numero, nombre, vencimiento, cvv, hoy=None):
    hoy = hoy or date.today()
    errores = {}
    n = _digitos(numero)
    if not (13 <= len(n) <= 19) or not luhn_ok(n):
        errores["numero"] = "El número de tarjeta no es válido."
    if not _NOMBRE.match((nombre or "").strip()):
        errores["nombre"] = "Poné el nombre como figura en la tarjeta."
    m = re.match(r"^(0[1-9]|1[0-2])\s*/\s*(\d{2})$", (vencimiento or "").strip())
    if not m:
        errores["vencimiento"] = "Usá el formato MM/AA."
    elif (2000 + int(m.group(2)), int(m.group(1))) < (hoy.year, hoy.month):
        errores["vencimiento"] = "La tarjeta está vencida."
    largo_cvv = 4 if n[:2] in ("34", "37") else 3  # American Express usa 4
    if not re.fullmatch(rf"\d{{{largo_cvv}}}", (cvv or "").strip()):
        errores["cvv"] = f"El código de seguridad tiene {largo_cvv} dígitos."
    return errores


def validar_transferencia(banco, cuenta, titular, documento):
    errores = {}
    if banco not in BANCOS:
        errores["banco"] = "Elegí tu banco."
    if not 6 <= len(_digitos(cuenta)) <= 15:
        errores["cuenta"] = "El número de cuenta debe tener entre 6 y 15 dígitos."
    if not _NOMBRE.match((titular or "").strip()):
        errores["titular"] = "Poné el nombre del titular."
    if not ci_valida(documento):
        errores["documento"] = "La cédula no es válida (ej. 1.234.567-2)."
    return errores


def validar_mercadopago(contacto):
    contacto = (contacto or "").strip()
    if _EMAIL.match(contacto):
        return {}
    d = _digitos(contacto)
    if d.startswith("598") and len(d) == 11:
        d = "0" + d[3:]
    if re.fullmatch(r"09\d{7}", d):
        return {}
    return {"contacto": "Poné el email o el celular (09X XXX XXX) de tu cuenta de Mercado Pago."}


if __name__ == "__main__":
    assert ci_valida("1.234.567-2") and not ci_valida("1.234.567-3") and not ci_valida("123")
    assert luhn_ok("4242424242424242") and not luhn_ok("4242424242424243")
    hoy = date(2026, 10, 27)
    assert validar_tarjeta("4242 4242 4242 4242", "Gonzalo Perez", "10/26", "123", hoy) == {}   # vence fin de mes: vale
    assert set(validar_tarjeta("4242 4242 4242 4242", "Gonzalo", "09/26", "12", hoy)) == {"vencimiento", "cvv"}
    assert validar_tarjeta("3782 822463 10005", "Ana Gómez", "01/30", "1234", hoy) == {}        # Amex: CVV de 4
    assert set(validar_tarjeta("1234 5678 9012 3456", "", "13/30", "123", hoy)) == {"numero", "nombre", "vencimiento"}
    assert validar_transferencia("BROU", "001234567", "Ana Gómez", "1.234.567-2") == {}
    assert set(validar_transferencia("X", "12", "A", "1.234.567-9")) == {"banco", "cuenta", "titular", "documento"}
    assert validar_mercadopago("ana@correo.com") == {} and validar_mercadopago("+598 91 234 567") == {}
    assert validar_mercadopago("hola") != {}
    print("ok")
