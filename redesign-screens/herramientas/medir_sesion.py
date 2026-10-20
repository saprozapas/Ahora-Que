"""Medicion de las rutas CON SESION de main (solo lectura: login y GET).

Las credenciales se leen de las variables de entorno AQ_USUARIO y AQ_CLAVE
(nunca se escriben en un archivo ni se imprimen). Reutiliza el JS de medir.py.

Uso:
  AQ_USUARIO=... AQ_CLAVE=... python medir_sesion.py <base_url> <carpeta_salida> [descubrir]
  VPS="320x640,375x812,768x1024,1440x900"  (opcional)
Con el argumento "descubrir" solo lista las rutas con ID que tiene la cuenta.
"""
import json, os, pathlib, re, sys
from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], pathlib.Path(sys.argv[2])
SOLO_DESCUBRIR = len(sys.argv) > 3 and sys.argv[3] == "descubrir"
USUARIO, CLAVE = os.environ.get("AQ_USUARIO", ""), os.environ.get("AQ_CLAVE", "")

fuente = (pathlib.Path(__file__).parent / "medir.py").read_text(encoding="utf-8")
JS = re.search(r'JS = r"""(.*?)"""', fuente, re.S).group(1)
VIEWPORTS = [(320, 640), (375, 812), (768, 1024), (1440, 900)]
if os.environ.get("VPS"):
    VIEWPORTS = [tuple(int(n) for n in v.split("x")) for v in os.environ["VPS"].split(",")]
TEMAS = os.environ.get("TEMAS", "claro,noche").split(",")
FILTRO = os.environ.get("SOLO_RUTAS")  # subcadenas separadas por coma


UUIDS = []


def slug(ruta):
    def sub(m):
        if m.group(0) not in UUIDS:
            UUIDS.append(m.group(0))
        return "u%d" % (UUIDS.index(m.group(0)) + 1)
    ruta = re.sub(r"/social/p/[0-9a-zA-Z-]+", "/social/p/pub", ruta)
    ruta = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", sub, ruta)
    return re.sub(r"[^a-z0-9]+", "-", ruta.lower()).strip("-") or "inicio"


ESTADO = os.environ.get("AQ_ESTADO")  # archivo de sesion de Playwright: evita volver a iniciar sesion


def entrar(ctx):
    pg = ctx.new_page()
    if ESTADO:
        pg.goto(BASE + "/dashboard", wait_until="networkidle")
        return pg, "/login" not in pg.url
    pg.goto(BASE + "/login", wait_until="networkidle")
    pg.fill("input[name=username]", USUARIO)
    pg.fill("input[name=password]", CLAVE)
    pg.click("form button[type=submit], form input[type=submit]")
    pg.wait_for_load_state("networkidle")
    ok = "/login" not in pg.url
    return pg, ok


def hrefs(pg, ruta, patron):
    pg.goto(BASE + ruta, wait_until="networkidle")
    pg.wait_for_timeout(800)
    todo = pg.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))")
    vistos = []
    for h in todo:
        if re.fullmatch(patron, h or "") and h not in vistos:
            vistos.append(h)
    return vistos


def descubrir(pg):
    d = {}
    d["grupos"] = hrefs(pg, "/grupos", r"/grupos/(?!nuevo)[0-9a-fA-F-]{8,}")
    planes = []
    for r in ("/planes/confirmados", "/planes/grupo", "/planes/guardados", "/planes/archivados"):
        planes += [h for h in hrefs(pg, r, r"/planes/[0-9a-fA-F-]{8,}") if h not in planes]
    d["planes"] = planes
    d["usuarios"] = hrefs(pg, "/amigos", r"/usuarios/[0-9a-fA-F-]{8,}")
    pg.goto(BASE + "/social?tab=amigos", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    d["publicaciones"] = [h for h in pg.evaluate("[...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'))")
                          if re.fullmatch(r"/social/p/[0-9a-zA-Z-]+", h or "")][:2]
    if not d["publicaciones"]:
        # El feed se arma por JS: se leen los ids con el mismo GET que usa la pagina.
        for pestana in ("amigos", "descubrir"):
            j = pg.evaluate(f"fetch('/social/feed?pestana={pestana}&limite=2').then(r=>r.json())")
            d["publicaciones"] += ["/social/p/" + str(x["id"]) for x in j.get("publicaciones", [])][:1]
    if d["grupos"]:
        g = d["grupos"][0]
        d["racha"] = hrefs(pg, g, r"/racha/[0-9a-fA-F-]{8,}")[:1]
    return d


def rutas(d):
    r = ["/dashboard", "/social?tab=amigos", "/social?tab=descubrir", "/social?tab=actividad", "/calendario",
         "/amigos", "/grupos", "/grupos/nuevo", "/inbox?tab=solicitudes",
         "/planes/", "/planes/confirmados", "/planes/grupo", "/planes/guardados", "/planes/archivados",
         "/planes/nueva-idea/asistente", "/planes/nueva-idea", "/perfil", "/perfil/cambiar-contrasena",
         "/social/moderacion"]
    for g in d.get("grupos", [])[:2]:
        r.append(g)
    if d.get("grupos"):
        g = d["grupos"][0]
        r += [g + "/chat", g + "/postular", g + "/asistente", g + "/encuestas/nueva"]
    r += d.get("racha", [])[:1]
    r += d.get("planes", [])[:2]
    r += d.get("usuarios", [])[:1]
    r += d.get("publicaciones", [])[:2]
    return r


with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    ctx = nav.new_context(viewport={"width": 375, "height": 812}, locale="es-UY", **({"storage_state": ESTADO} if ESTADO else {}))
    pg, ok = entrar(ctx)
    print("login ok:", ok, "->", pg.url.replace(BASE, ""), flush=True)
    if not ok:
        sys.exit(2)
    d = descubrir(pg)
    # Inbox: la pestana de publicaciones marca avisos como leidos (escribe). Solo se visita si no hay avisos nuevos.
    pg.goto(BASE + "/inbox?tab=solicitudes", wait_until="networkidle")
    nuevos = pg.evaluate("document.querySelectorAll('.inbox-tabs a[href*=publicaciones] .group-tab-count').length")
    d["inbox_avisos_nuevos_detectados"] = nuevos
    ctx.close()
    lista = rutas(d)
    if nuevos == 0:
        lista.append("/inbox?tab=publicaciones")
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in d.items()}, ensure_ascii=False), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "rutas_medidas.json").write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    if SOLO_DESCUBRIR:
        print(json.dumps(lista, ensure_ascii=False, indent=1)); nav.close(); sys.exit(0)
    for _r in lista:
        slug(_r)  # fija u1, u2... segun la lista completa
    if FILTRO:
        lista = [r for r in lista if any(f in r for f in FILTRO.split(","))]
    for tema in TEMAS:
        for (w, h) in VIEWPORTS:
            ctx = nav.new_context(viewport={"width": w, "height": h}, locale="es-UY", **({"storage_state": ESTADO} if ESTADO else {}))
            if tema == "noche":
                ctx.add_init_script("try{localStorage.setItem('ahoraque-theme','night')}catch(e){}")
            pg, ok = entrar(ctx)
            if not ok:
                print("login fallo", w, tema, flush=True); ctx.close(); continue
            for ruta in lista:
                datos = None
                for intento in (1, 2, 3):
                    try:
                        resp = pg.goto(BASE + ruta, wait_until="networkidle", timeout=45000)
                        if resp is not None and resp.status >= 500:
                            raise RuntimeError("HTTP %d" % resp.status)
                        pg.wait_for_timeout(900)
                        alto = pg.evaluate("document.documentElement.scrollHeight")
                        y = 0
                        while y < alto:
                            pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(100); y += h // 2
                        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(900)
                        datos = pg.evaluate(JS)
                        break
                    except Exception as ex:
                        print("reintento", intento, ruta[:40], str(ex)[:70].replace(chr(10), " "), flush=True)
                        pg.wait_for_timeout(6000)
                if datos is None:
                    print("SIN DATOS", ruta[:60], w, tema, flush=True)
                    continue
                datos["ruta"] = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", "<uuid>", re.sub(r"/social/p/[0-9a-zA-Z-]+", "/social/p/<id>", ruta))
                datos["viewport"] = f"{w}x{h}"; datos["tema"] = tema
                datos["urlFinal"] = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}", "<uuid>", pg.url.replace(BASE, ""))
                datos["estado"] = pg.evaluate("document.title")
                c = OUT / slug(ruta); c.mkdir(parents=True, exist_ok=True)
                (c / f"medicion__{w}__{tema}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
                if w in (375, 1440):
                    pg.screenshot(path=str(c / f"carga__{w}__{tema}.png"), full_page=True)
            ctx.close()
            print("ok", w, tema, flush=True)
    nav.close()
