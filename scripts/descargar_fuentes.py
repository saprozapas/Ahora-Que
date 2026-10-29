"""Descarga las fuentes de Google Fonts (Figtree y Fraunces) y las guarda en el propio proyecto.

Se corre UNA vez, con internet:

    python scripts/descargar_fuentes.py

Qué hace:
  1. Pide a Google el CSS de las dos familias (pidiendo formato woff2).
  2. Descarga cada archivo .woff2 a static/fonts/.
  3. Escribe static/css/fuentes.css apuntando a esos archivos locales.

Después de correrlo, subí a git static/fonts/ y static/css/fuentes.css. Desde ese momento las visitas
dejan de pedirle las fuentes a Google (y de enviarle su IP).
"""
import pathlib
import re
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent
URL = (
    "https://fonts.googleapis.com/css2?family=Figtree:wght@400..800"
    "&family=Fraunces:opsz,wght@9..144,300..700&display=swap"
)
# Con un navegador moderno como User-Agent, Google responde con woff2.
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def pedir(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as respuesta:
        return respuesta.read()


def main():
    carpeta_fuentes = RAIZ / "static" / "fonts"
    carpeta_fuentes.mkdir(parents=True, exist_ok=True)

    css = pedir(URL).decode("utf-8")
    bloques = re.findall(r"(?:/\*.*?\*/\s*)?@font-face\s*\{.*?\}", css, flags=re.S)
    if not bloques:
        raise SystemExit("No se encontraron bloques @font-face: Google cambió el formato.")

    salida = ["/* Generado por scripts/descargar_fuentes.py: fuentes alojadas en este sitio. */\n"]
    for numero, bloque in enumerate(bloques, start=1):
        familia = re.search(r"font-family:\s*'([^']+)'", bloque).group(1).lower()
        url = re.search(r"url\((https://[^)]+)\)", bloque).group(1)
        nombre = f"{familia}-{numero}.woff2"
        (carpeta_fuentes / nombre).write_bytes(pedir(url))
        salida.append(re.sub(r"/\*.*?\*/\s*", "", bloque.replace(url, f"../fonts/{nombre}"), flags=re.S) + "\n")
        print("Descargada:", nombre)

    (RAIZ / "static" / "css" / "fuentes.css").write_text("\n".join(salida), encoding="utf-8")
    print("Listo: static/css/fuentes.css")


if __name__ == "__main__":
    main()
