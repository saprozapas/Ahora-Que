"""Capturas de todas las pantallas de Ahora Qué, para comparar antes/después
del rediseño.

Uso:
    python redesign-screens/capturar.py antes
    python redesign-screens/capturar.py despues --tema noche

Solo navega (GET) y saca capturas: no envía formularios, salvo el de login
cuando hay credenciales. Las rutas con sesión se capturan solo si están
definidas AQ_USUARIO y AQ_CLAVE en el entorno (nunca se escriben en un
archivo). La app tiene que estar corriendo en AQ_URL (por defecto
http://127.0.0.1:5057).

Usa el Edge instalado en Windows (channel="msedge"), porque la descarga del
Chromium de Playwright se corta por timeout en esta máquina.
"""

import argparse
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ANCHOS = (375, 1440)
ALTO = 900

PUBLICAS = [
    ("landing", "/"),
    ("explorar", "/explorar"),
    ("plan-ejemplo", "/plan/caminata-atardecer"),
    ("contacto", "/contacto"),
    ("login", "/login"),
    ("registro", "/register"),
]

CON_SESION = [
    ("dashboard", "/dashboard"),
    ("inbox", "/inbox"),
    ("grupos", "/grupos"),
    ("grupos-nuevo", "/grupos/nuevo"),
    ("amigos", "/amigos"),
    ("social", "/social"),
    ("perfil", "/perfil"),
    ("cambiar-contrasena", "/perfil/cambiar-contrasena"),
    ("planes", "/planes/"),
    ("planes-confirmados", "/planes/confirmados"),
    ("planes-grupo", "/planes/grupo"),
    ("planes-guardados", "/planes/guardados"),
    ("planes-archivados", "/planes/archivados"),
    ("planes-nueva-idea", "/planes/nueva-idea"),
    ("calendario", "/calendario"),
]

PLAN_ID = re.compile(r"^/planes/[0-9a-fA-F-]{8,}$")


def preparar(pagina):
    # Muestra todo lo que la página revela al hacer scroll, para que la
    # captura de página completa no salga con secciones en blanco.
    pagina.evaluate(
        """() => document.querySelectorAll('.scroll-reveal')
                  .forEach((el) => el.classList.add('is-visible'))"""
    )
    pagina.wait_for_timeout(600)


def capturar(pagina, base, ruta, destino):
    respuesta = pagina.goto(base + ruta, wait_until="networkidle")
    preparar(pagina)
    pagina.screenshot(path=str(destino), full_page=True)
    ancho_doc = pagina.evaluate("document.documentElement.scrollWidth")
    ancho_vista = pagina.viewport_size["width"]
    estado = respuesta.status if respuesta else "?"
    aviso = "  <- scroll horizontal" if ancho_doc > ancho_vista else ""
    print(f"  {destino.name:<34} {estado}  {pagina.url[len(base):]}{aviso}")


def primer_link(pagina, base, ruta, condicion):
    pagina.goto(base + ruta, wait_until="networkidle")
    for href in pagina.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))"):
        if href and condicion(href):
            return href
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("carpeta", choices=["antes", "despues"])
    parser.add_argument("--tema", choices=["claro", "noche"], default="claro")
    args = parser.parse_args()

    base = os.environ.get("AQ_URL", "http://127.0.0.1:5057").rstrip("/")
    usuario = os.environ.get("AQ_USUARIO")
    clave = os.environ.get("AQ_CLAVE")

    salida = Path(__file__).parent / args.carpeta
    salida.mkdir(parents=True, exist_ok=True)
    sufijo_tema = "" if args.tema == "claro" else "-noche"

    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge")

        for ancho in ANCHOS:
            contexto = navegador.new_context(
                viewport={"width": ancho, "height": ALTO},
                reduced_motion="reduce",
            )
            if args.tema == "noche":
                contexto.add_init_script(
                    "try { localStorage.setItem('ahoraque-theme', 'night') } catch (e) {}"
                )
            pagina = contexto.new_page()
            print(f"\n{ancho}px, tema {args.tema}")

            for nombre, ruta in PUBLICAS:
                capturar(pagina, base, ruta, salida / f"{nombre}-{ancho}{sufijo_tema}.png")

            if not (usuario and clave):
                print("  (sin AQ_USUARIO/AQ_CLAVE: se saltean las rutas con sesión)")
                contexto.close()
                continue

            pagina.goto(base + "/login", wait_until="networkidle")
            pagina.fill("#username", usuario)
            pagina.fill("#password", clave)
            with pagina.expect_navigation():
                pagina.click("form.auth-form button[type=submit]")
            if "/login" in pagina.url:
                print("  El login falló: revisá AQ_USUARIO y AQ_CLAVE.")
                sys.exit(1)

            rutas = list(CON_SESION)

            grupo = primer_link(
                pagina, base, "/grupos",
                lambda h: h.startswith("/grupos/") and h.count("/") == 2 and h != "/grupos/nuevo",
            )
            if grupo:
                rutas += [("grupo", grupo), ("grupo-postular", grupo + "/postular")]
                usuario_link = primer_link(pagina, base, grupo, lambda h: h.startswith("/usuarios/"))
                if usuario_link:
                    rutas.append(("perfil-publico", usuario_link))

            plan = None
            for lista in ("/planes/confirmados", "/planes/grupo", "/planes/guardados", "/planes/archivados"):
                plan = primer_link(pagina, base, lista, lambda h: bool(PLAN_ID.match(h)))
                if plan:
                    break
            if plan:
                rutas.append(("plan-detalle", plan))

            for nombre, ruta in rutas:
                capturar(pagina, base, ruta, salida / f"{nombre}-{ancho}{sufijo_tema}.png")

            contexto.close()

        navegador.close()


if __name__ == "__main__":
    main()
