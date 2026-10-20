"""Paridad funcional entre dos instancias de la app (por ejemplo main vs la rama Sereno).

Para cada ruta baja el HTML de las dos (con la misma cuenta, solo GET) y compara
lo que importa para que la pantalla FUNCIONE igual: enlaces, formularios (accion,
metodo, data-confirmar), controles (name/type), ids, atributos data-* y scripts.
No compara clases ni estilos.

Uso: AQ_USUARIO=... AQ_CLAVE=... python paridad.py <urlA> <urlB> <rutas.json>
"""
import json, os, re, sys
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

A, B, RUTAS = sys.argv[1], sys.argv[2], sys.argv[3]
USUARIO, CLAVE = os.environ["AQ_USUARIO"], os.environ["AQ_CLAVE"]


class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.forms, self.controles, self.ids, self.datas, self.scripts, self.estilos = set(), set(), set(), set(), set(), set(), set()
        self.h1 = 0
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and a["id"]:
            self.ids.add(a["id"])
        for k in a:
            if k.startswith("data-") and k not in ("data-aqi",):
                self.datas.add(k)
        if tag == "a" and a.get("href") and not a["href"].startswith("#"):
            self.links.add(re.sub(r"\?v=[^&\"']*", "", a["href"]))
        if tag == "form":
            self.forms.add((a.get("action", ""), (a.get("method") or "get").lower(), a.get("data-confirmar", "")))
        if tag in ("input", "select", "textarea", "button") and (a.get("name") or tag == "button"):
            tipo = a.get("type", "") if tag != "textarea" else "textarea"
            if tag == "input" and tipo == "hidden":
                self.controles.add(("hidden", a.get("name", ""), ""))
            elif a.get("name"):
                self.controles.add((tag, a.get("name", ""), tipo))
        if tag == "script" and a.get("src"):
            self.scripts.add(re.sub(r"\?.*", "", a["src"]))
        if tag == "link" and a.get("rel") == "stylesheet":
            self.estilos.add(re.sub(r"\?.*", "", a.get("href", "")))
        if tag == "h1":
            self.h1 += 1


def bajar(ctx, ruta):
    r = ctx.get(ruta, max_redirects=5)
    return r.status, r.text()


def sesion(p, base):
    ctx = p.request.new_context(base_url=base)
    ctx.post("/login", form={"username": USUARIO, "password": CLAVE})
    return ctx


with sync_playwright() as p:
    ca, cb = sesion(p, A), sesion(p, B)
    rutas = json.load(open(RUTAS, encoding="utf-8"))
    # paginas publicas
    todas = ["/", "/login", "/register", "/explorar", "/contacto", "/plan/caminata-atardecer", "/terminos"] + rutas
    resumen = []
    for ruta in todas:
        publica = ruta in ("/", "/login", "/register", "/explorar", "/contacto", "/plan/caminata-atardecer", "/terminos")
        ra = ca if True else None
        sa, ha = bajar(ca, ruta); sb, hb = bajar(cb, ruta)
        ea, eb = Extractor(), Extractor()
        ea.feed(ha); eb.feed(hb)
        d = {}
        for nombre in ("links", "forms", "controles", "ids", "datas", "scripts"):
            fa, fb = getattr(ea, nombre), getattr(eb, nombre)
            falt, sobr = sorted(fa - fb, key=str), sorted(fb - fa, key=str)
            if falt or sobr:
                d[nombre] = {"faltan_en_B": falt, "sobran_en_B": sobr}
        resumen.append({"ruta": re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "<uuid>", ruta), "status": [sa, sb], "h1": [ea.h1, eb.h1], "dif": d})
    print(json.dumps(resumen, ensure_ascii=False, indent=1))
