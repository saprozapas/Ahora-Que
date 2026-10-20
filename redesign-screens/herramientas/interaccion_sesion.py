"""Interaccion, teclado y zoom sobre las rutas con SESION de main.

Solo lectura: todo request que no sea GET (salvo el POST de /login) se ABORTA
en el contexto del navegador, asi que ningun clic puede escribir en la base.
Credenciales: variables de entorno AQ_USUARIO y AQ_CLAVE (no se guardan).

Uso: python interaccion_sesion.py <base_url> <carpeta_salida> <parte> [rutas_json]
  parte: foco | dialogos | carrusel | teclado | zoom
"""
import json, os, pathlib, re, sys
from playwright.sync_api import sync_playwright

BASE, OUT, PARTE = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
RUTAS_JSON = sys.argv[4] if len(sys.argv) > 4 else "redesign-screens/audit/sesion-main/rutas_medidas.json"
USUARIO, CLAVE = os.environ["AQ_USUARIO"], os.environ["AQ_CLAVE"]
OUT.mkdir(parents=True, exist_ok=True)
BLOQUEADOS = []


def anon(t):
    t = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "<uuid>", t)
    return re.sub(r"/social/p/[0-9a-zA-Z-]+", "/social/p/<id>", t)


def bloquear(route):
    r = route.request
    if r.method in ("GET", "HEAD", "OPTIONS") or (r.method == "POST" and r.url.endswith("/login")):
        route.continue_()
    else:
        BLOQUEADOS.append((r.method, anon(r.url.replace(BASE, ""))))
        route.abort()


def contexto(nav, w, h, noche=False, **kw):
    ctx = nav.new_context(viewport={"width": w, "height": h}, locale="es-UY", **kw)
    if noche:
        ctx.add_init_script("try{localStorage.setItem('ahoraque-theme','night')}catch(e){}")
    ctx.route("**/*", bloquear)
    pg = ctx.new_page()
    pg.goto(BASE + "/login", wait_until="networkidle")
    pg.fill("input[name=username]", USUARIO)
    pg.fill("input[name=password]", CLAVE)
    pg.click("form button[type=submit]")
    pg.wait_for_load_state("networkidle")
    assert "/login" not in pg.url, "login fallo"
    return ctx, pg


def ir(pg, ruta, esperar=900):
    for intento in (1, 2, 3):
        try:
            r = pg.goto(BASE + ruta, wait_until="networkidle", timeout=45000)
            if r is not None and r.status >= 500:
                raise RuntimeError("HTTP %d" % r.status)
            pg.wait_for_timeout(esperar)
            return True
        except Exception as ex:
            print("reintento", intento, anon(ruta)[:50], str(ex)[:60].replace(chr(10), " "), flush=True)
            pg.wait_for_timeout(5000)
    return False


def volcar(nombre, datos):
    (OUT / nombre).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


rutas = json.loads(pathlib.Path(RUTAS_JSON).read_text(encoding="utf-8"))
G1 = next((r for r in rutas if re.fullmatch(r"/grupos/[0-9a-f-]{36}", r)), None)

# ---------------------------------------------------------------- FOCO
JS_PREP = r"""() => {
  const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex],[contenteditable=true]';
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const snap = s => ({ ol: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor, sh: s.boxShadow, bc: s.borderTopColor, bw: s.borderTopWidth, bg: s.backgroundColor, c: s.color, td: s.textDecorationLine });
  const els = [...document.querySelectorAll(sel)].filter(e => !e.disabled && e.tabIndex >= 0 && !e.closest('[inert]') && !e.closest('dialog:not([open])'));
  window.__aq = {};
  els.forEach((e, i) => { e.setAttribute('data-aqi', i); window.__aq[i] = { vis: vis(e), base: snap(getComputedStyle(e)) }; });
  return { total: els.length, visibles: els.filter(vis).length };
}"""
JS_FOCO = r"""() => {
  const a = document.activeElement; if (!a || a === document.body || a === document.documentElement) return { body: true, i: -1 };
  window.__aqn = window.__aqn || 0; if (!a.__aqk) a.__aqk = ++window.__aqn;
  const i = a.getAttribute('data-aqi'); const m = window.__aq[i]; const s = getComputedStyle(a); const r = a.getBoundingClientRect();
  const now = { ol: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor, sh: s.boxShadow, bc: s.borderTopColor, bw: s.borderTopWidth, bg: s.backgroundColor, c: s.color, td: s.textDecorationLine };
  const ch = m ? Object.keys(now).filter(k => now[k] !== m.base[k]) : [];
  const olVisible = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 && !/rgba\(\d+, \d+, \d+, 0\)/.test(s.outlineColor);
  const W = innerWidth, H = innerHeight;
  const tapa = [...document.querySelectorAll('*')].filter(e => ['fixed', 'sticky'].includes(getComputedStyle(e).position) && !e.contains(a) && !a.contains(e)).filter(e => { const q = e.getBoundingClientRect(); return q.width > 40 && q.height > 10 && q.left < r.right && q.right > r.left && q.top < r.bottom && q.bottom > r.top; }).map(e => e.tagName.toLowerCase() + '.' + [...e.classList].slice(0, 2).join('.'));
  return { key: a.__aqk, i: i === null ? -1 : +i, tag: a.tagName.toLowerCase(), cls: [...a.classList].slice(0, 3).join('.'), txt: (a.getAttribute('aria-label') || a.innerText || a.value || '').trim().slice(0, 28),
    top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), enVista: r.top >= 0 && r.bottom <= H && r.left >= 0 && r.right <= W, visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden',
    outline: olVisible ? s.outlineWidth + ' ' + s.outlineStyle + ' ' + s.outlineColor : null, cambios: ch, tapadoPor: tapa };
}"""


def parte_foco(nav):
    res = {}
    ctx, pg = contexto(nav, 1440, 900)
    for ruta in rutas:
        if not ir(pg, ruta):
            res[anon(ruta)] = {"error": "no cargo"}; continue
        pg.evaluate(JS_PREP)
        pg.evaluate("document.activeElement && document.activeElement.blur(); window.scrollTo(0,0)")
        pg.keyboard.press("Tab")
        primero = pg.evaluate(JS_FOCO)
        skip = {"primerFoco": primero.get("cls"), "esSkipLink": "skip-link" in (primero.get("cls") or ""), "visibleAlEnfocar": primero.get("enVista")}
        pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
        skip["hash"] = pg.evaluate("location.hash")
        pg.keyboard.press("Tab")
        skip["tabDespuesDelSalto"] = pg.evaluate("(()=>{const a=document.activeElement;return {enMain: !!a.closest('#contenido'), tag:a.tagName.toLowerCase(), cls:[...a.classList].slice(0,2).join('.')}})()")
        ir(pg, ruta, 800)
        prep = pg.evaluate(JS_PREP)
        pasos, vistos, claves, extra, sin_ind, debil, tapados, invisibles = [], set(), set(), [], [], [], [], []
        prev_top = None; saltos_atras = 0
        maximo = min(prep["total"] + 25, 220)
        for k in range(maximo):
            pg.keyboard.press("Tab")
            pg.wait_for_timeout(280)  # las transiciones de foco duran ~160 ms; sin esperar se mide el estado inicial
            f = pg.evaluate(JS_FOCO)
            if f.get("body"):
                if k > 2:
                    break
                continue
            if f["key"] in claves:
                break
            claves.add(f["key"]); pasos.append(f["key"])
            if f["i"] != -1:
                vistos.add(f["i"])
            else:
                extra.append(f"{f['tag']}.{f['cls']} (no listado: enfocable por el navegador)")
            tiene_ind = f["outline"] is not None or any(c in f["cambios"] for c in ("sh", "bc", "bg", "td"))
            if not tiene_ind:
                sin_ind.append(f"{f['tag']}.{f['cls']} '{f['txt']}'" + (" (solo color de texto)" if "c" in f["cambios"] else ""))
            elif f["outline"] is None and f["cambios"]:
                debil.append(f"{f['tag']}.{f['cls']} '{f['txt']}' cambia {f['cambios']}")
            if not f["visible"]:
                invisibles.append(f"{f['tag']}.{f['cls']} '{f['txt']}'")
            if f["tapadoPor"]:
                tapados.append(f"{f['tag']}.{f['cls']} '{f['txt']}' <- {f['tapadoPor'][:2]}")
            absolute_top = f["top"] + pg.evaluate("scrollY")
            if prev_top is not None and absolute_top < prev_top - 300:
                saltos_atras += 1
            prev_top = absolute_top
        inalc = pg.evaluate("Object.entries(window.__aq).filter(([i,m])=>m.vis).map(([i,m])=>+i)")
        no_alcanzados = [i for i in inalc if i not in vistos]
        nombres = pg.evaluate("(l)=>l.map(i=>{const e=document.querySelector('[data-aqi=\"'+i+'\"]');return e.tagName.toLowerCase()+'.'+[...e.classList].slice(0,2).join('.')+' \"'+(e.getAttribute('aria-label')||e.innerText||'').trim().slice(0,22)+'\"'})", no_alcanzados[:8])
        res[anon(ruta)] = {"focusables": prep["total"], "visibles": prep["visibles"], "tabs": len(pasos), "skipLink": skip,
                           "sinIndicador": sin_ind, "indicadorDebil": debil[:8], "focoInvisible": invisibles, "tapadoPorFijos": tapados[:6],
                           "saltosAtrasDe300px": saltos_atras, "enfocablesNoListados": extra[:8], "visiblesNoAlcanzadosPorTab": len(no_alcanzados), "ejemplosNoAlcanzados": nombres}
        print("foco", anon(ruta)[:44], "tabs", len(pasos), "sinInd", len(sin_ind), "noAlcanz", len(no_alcanzados), flush=True)
    volcar("foco.json", res); ctx.close()


# ---------------------------------------------------------------- DIALOGOS
JS_DLG = r"""() => {
  const ds = [...document.querySelectorAll('dialog[open]')]; const d = ds[ds.length - 1]; if (!d) return { abierto: false };
  const foc = [...d.querySelectorAll('a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; });
  const r = d.getBoundingClientRect(), s = getComputedStyle(d), H = innerHeight, W = innerWidth, a = document.activeElement;
  const cuerpo = d.querySelector('.modal-body, form') || d;
  const botones = foc.filter(e => e.tagName === 'BUTTON' || e.type === 'submit');
  const ult = botones[botones.length - 1];
  const sc = [d, cuerpo, ...d.querySelectorAll('*')].filter(e => ['auto', 'scroll'].includes(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 1);
  return { abierto: true, id: d.id || '(generado)', clase: d.className.slice(0, 30), nombreAccesible: !!(d.getAttribute('aria-label') || d.getAttribute('aria-labelledby')),
    alto: Math.round(r.height), ancho: Math.round(r.width), top: Math.round(r.top), bottom: Math.round(r.bottom), viewport: W + 'x' + H, masAltoQueVista: r.height > H - 4,
    hayScrollInterno: sc.length > 0, overflowY: s.overflowY, maxHeight: s.maxHeight, focusables: foc.length,
    focoInicial: a && d.contains(a) ? (a.tagName.toLowerCase() + '.' + [...a.classList].slice(0, 2).join('.') + ' "' + (a.getAttribute('aria-label') || a.innerText || a.name || '').trim().slice(0, 24) + '"') : (a ? 'FUERA: ' + a.tagName.toLowerCase() : 'ninguno'),
    focoInicialDentro: !!(a && d.contains(a)),
    ultimoBotonVisibleSinScroll: ult ? (ult.getBoundingClientRect().bottom <= H && ult.getBoundingClientRect().top >= 0) : null,
    ultimoBotonBottom: ult ? Math.round(ult.getBoundingClientRect().bottom) : null,
    controlesMenoresA44: foc.filter(e => { const q = e.getBoundingClientRect(); return q.width < 44 || q.height < 44; }).length };
}"""
JS_TRAMPA = r"""() => { const d = [...document.querySelectorAll('dialog[open]')].pop(); const a = document.activeElement; return { dentro: !!(d && a && d.contains(a)), el: a ? a.tagName.toLowerCase() + '.' + [...a.classList].slice(0, 2).join('.') : null }; }"""


def probar_dialogo(pg, nombre, abrir, vp):
    r = {"nombre": nombre, "vp": vp}
    pg.evaluate("document.querySelectorAll('[data-aq-opener]').forEach(e=>e.removeAttribute('data-aq-opener'))")
    try:
        abrir()
    except Exception as ex:
        r["error"] = "no se pudo abrir: " + str(ex)[:80].replace(chr(10), " "); return r
    pg.wait_for_timeout(700)
    r.update(pg.evaluate(JS_DLG))
    if not r.get("abierto"):
        return r
    if vp.startswith("375"):
        fuera = 0
        for _ in range(min(r["focusables"] + 4, 25)):
            pg.keyboard.press("Tab")
            if not pg.evaluate(JS_TRAMPA)["dentro"]:
                fuera += 1
        for _ in range(3):
            pg.keyboard.press("Shift+Tab")
        r["trampaDeFoco"] = {"tabsQueSalieronDelDialogo": fuera, "shiftTabDentro": pg.evaluate(JS_TRAMPA)["dentro"]}
        pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
        r["escCierra"] = not pg.evaluate("!!document.querySelector('dialog[open]')")
        r["focoVuelveAlDisparador"] = pg.evaluate("(()=>{const a=document.activeElement;return !!(a&&a.hasAttribute('data-aq-opener'))})()")
        r["focoFinal"] = pg.evaluate("(()=>{const a=document.activeElement;return a?a.tagName.toLowerCase()+'.'+[...a.classList].slice(0,2).join('.'):null})()")
        try:
            abrir(); pg.wait_for_timeout(600)
            pg.mouse.click(2, 2); pg.wait_for_timeout(400)
            r["clicAfueraCierra"] = not pg.evaluate("!!document.querySelector('dialog[open]')")
        except Exception as ex:
            r["clicAfuera"] = "n/d " + str(ex)[:50]
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    else:
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
    return r


def marcar(pg, sel):
    return pg.evaluate("(s)=>{const e=[...document.querySelectorAll(s)].find(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0});if(!e)return false;e.setAttribute('data-aq-opener','1');return true}", sel)


def abridor(pg, sel):
    def f():
        if not marcar(pg, sel):
            raise RuntimeError("sin disparador " + sel)
        pg.locator("[data-aq-opener]").first.click(timeout=5000)
    return f


def parte_dialogos(nav):
    res = []
    casos = []
    if G1:
        casos += [(G1, "grupo: editar grupo", '[data-modal-open="modal-editar-grupo"]'),
                  (G1, "grupo: invitar", '[data-modal-open="modal-invitar"]'),
                  (G1, "grupo: abandonar", '[data-modal-open="modal-abandonar-grupo"]'),
                  (G1, "grupo: integrantes", '[data-modal-open="modal-integrantes"]'),
                  (G1, "preguntar: cerrar votacion (data-confirmar)", 'form[data-confirmar] button'),
                  (G1.replace("/grupos/", "/racha/"), "racha: hito", '[data-modal-open^="modal-hito-"]')]
    casos += [("/amigos", "amigos: invitar a un grupo", '[data-modal-open="modal-invitar-grupo"]'),
              ("/amigos", "preguntar: eliminar amigo (data-confirmar)", 'form[data-confirmar] button'),
              ("/planes/guardados", "preguntar: quitar de guardados", 'form[data-confirmar] button'),
              ("/social?tab=amigos", "social: compartir un plan", '[data-modal-open="soc-modal-publicar"]'),
              ("/social?tab=amigos", "social: ver comentarios (dialogo de la publicacion)", '[data-soc-ver-comentarios]'),
              ("/social?tab=amigos", "social: proponer a mi grupo", '[data-soc-proponer]'),
              ("/social?tab=amigos", "social: reportar", '[data-soc-reportar]:not([hidden])'),
              ("/social?tab=descubrir", "social: abrir miniatura", '.soc-miniatura')]
    for r in rutas:
        if re.fullmatch(r"/planes/[0-9a-f-]{36}", r):
            casos.append((r, "preguntar: detalle de plan", 'form[data-confirmar] button')); break
    for (w, h) in [(375, 667), (320, 640), (720, 450)]:
        ctx, pg = contexto(nav, w, h)
        ruta_actual = None
        for ruta, nombre, sel in casos:
            if ruta != ruta_actual:
                if not ir(pg, ruta, 1500):
                    continue
                ruta_actual = ruta
                if "/social" in ruta:
                    pg.wait_for_timeout(2500)
            antes = len(BLOQUEADOS)
            r = probar_dialogo(pg, nombre, abridor(pg, sel), f"{w}x{h}")
            r["ruta"] = anon(ruta); r["requestsBloqueados"] = len(BLOQUEADOS) - antes
            res.append(r)
            print("dialogo", f"{w}x{h}", nombre[:44], "abierto" if r.get("abierto") else r.get("error", "no abrio"), flush=True)
            pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        ctx.close()
    volcar("dialogos.json", res)
    volcar("requests_bloqueados.json", sorted(set(BLOQUEADOS)))


# ---------------------------------------------------------------- CARRUSEL
JS_CARR = r"""() => [...document.querySelectorAll('[data-soc-fotos]:not([hidden])')].map((c, i) => { const t = c.closest('[data-publicacion-id]') || c.parentElement; const p = t.querySelector('[data-soc-puntos]');
  return { i, fotos: c.querySelectorAll('img').length, scrollW: c.scrollWidth, clientW: c.clientWidth, tabindex: c.getAttribute('tabindex'), role: c.getAttribute('role'), ariaLabel: c.getAttribute('aria-label'),
  snap: getComputedStyle(c).scrollSnapType, puntosTag: p && p.firstElementChild ? p.firstElementChild.tagName.toLowerCase() : null, puntosOcultos: p ? p.hidden : null,
  controles: [...t.querySelectorAll('button')].map(b => (b.getAttribute('aria-label') || b.innerText || '').trim().toLowerCase()).filter(x => /siguiente|anterior|next|prev/.test(x)) }; }).filter(x => x.fotos > 0)"""


def parte_carrusel(nav):
    res = {}
    ctx, pg = contexto(nav, 375, 812, has_touch=True, is_mobile=True)
    for pest in ("amigos", "descubrir"):
        ir(pg, f"/social?tab={pest}", 3000)
        info = pg.evaluate(JS_CARR)
        res[pest] = {"carruselesVisibles": len(info), "con2Fotos": [x for x in info if x["fotos"] > 1][:2], "con1Foto": len([x for x in info if x["fotos"] == 1])}
        idx = next((x["i"] for x in info if x["fotos"] > 1), None)
        if idx is None:
            continue
        carr = pg.locator('[data-soc-fotos]:not([hidden])').nth(idx)
        carr.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
        carr.evaluate("e=>e.setAttribute('data-aq-c','1')")
        pg.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
        alcanzable, k = False, 0
        for k in range(250):
            pg.keyboard.press("Tab")
            if pg.evaluate("!!document.activeElement && document.activeElement.hasAttribute('data-aq-c')"):
                alcanzable = True; break
        r = {"alcanzablePorTab": alcanzable, "tabsRecorridos": k + 1}
        if alcanzable:
            antes = carr.evaluate("e=>e.scrollLeft")
            pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(800)
            r["flechaDerechaMueve"] = carr.evaluate("e=>e.scrollLeft") != antes
        carr.evaluate("e=>e.scrollTo({left:e.clientWidth,behavior:'instant'})"); pg.wait_for_timeout(700)
        r["puntoActivoTrasDesplazar"] = pg.evaluate("(i)=>{const c=document.querySelectorAll('[data-soc-fotos]:not([hidden])')[i];const t=c.closest('[data-publicacion-id]')||c.parentElement;return [...t.querySelector('[data-soc-puntos]').children].map(x=>x.classList.contains('is-activo'))}", idx)
        r["altoCarrusel"] = carr.evaluate("e=>Math.round(e.getBoundingClientRect().height)")
        r["alts"] = carr.evaluate("e=>[...e.querySelectorAll('img')].map(i=>i.alt)")
        r["tamPuntos"] = pg.evaluate("(i)=>{const c=document.querySelectorAll('[data-soc-fotos]:not([hidden])')[i];const t=c.closest('[data-publicacion-id]')||c.parentElement;return [...t.querySelector('[data-soc-puntos]').children].map(x=>Math.round(x.getBoundingClientRect().width)+'x'+Math.round(x.getBoundingClientRect().height))}", idx)
        pg.screenshot(path=str(OUT / f"carrusel_{pest}_segunda_foto.png"))
        res[pest]["prueba"] = r
        print("carrusel", pest, r, flush=True)
    volcar("carrusel.json", res); ctx.close()


# ---------------------------------------------------------------- TECLADO (aproximacion por altura de viewport)
JS_CAMPO = r"""(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); const H = innerHeight;
  const fijos = [...document.querySelectorAll('*')].filter(x => ['fixed', 'sticky'].includes(getComputedStyle(x).position) && x.getBoundingClientRect().width > 100 && !x.contains(e));
  const tapa = fijos.filter(f => { const q = f.getBoundingClientRect(); return q.top < r.bottom && q.bottom > r.top; }).map(f => f.tagName.toLowerCase() + '.' + [...f.classList].slice(0, 2).join('.') + '[' + Math.round(f.getBoundingClientRect().top) + '-' + Math.round(f.getBoundingClientRect().bottom) + ']');
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), alto: Math.round(r.height), H, entero: r.top >= 0 && r.bottom <= H, tapadoPorFijo: tapa }; }"""


def parte_teclado(nav):
    res = []
    for H in (440, 340):
        ctx, pg = contexto(nav, 375, 812, has_touch=True, is_mobile=True)
        casos = []
        if G1:
            casos += [(G1 + "/chat", "chat de grupo: escribir", "#group-chat-input", "#group-chat-send", None),
                      (G1 + "/asistente", "asistente del grupo: escribir", "#chatbot-input", "#chatbot-enviar", None)]
        casos += [("/planes/nueva-idea", "nueva idea: buscar lugares", "#busqueda-texto", None, None),
                  ("/grupos/nuevo", "nuevo grupo: nombre", "form input[type=text]", "form button[type=submit]", None),
                  ("/perfil", "perfil: editar nombre", ".field-editable .field-edit input", None, ".field-editable .field-edit-btn"),
                  ("/social?tab=amigos", "social: compartir, texto", "dialog[open] textarea", None, '[data-modal-open="soc-modal-publicar"]')]
        for ruta, nombre, campo, boton, previo in casos:
            if not ir(pg, ruta, 1500):
                continue
            if "social" in ruta:
                pg.wait_for_timeout(2500)
            r = {"caso": nombre, "ruta": anon(ruta), "alturaVisibleSimulada": H}
            try:
                pg.set_viewport_size({"width": 375, "height": 812}); pg.wait_for_timeout(200)
                if previo:
                    marcar(pg, previo); pg.locator("[data-aq-opener]").first.click(timeout=4000); pg.wait_for_timeout(700)
                pg.set_viewport_size({"width": 375, "height": H}); pg.wait_for_timeout(300)
                pg.locator(campo).first.evaluate("e=>{e.blur();e.focus()}"); pg.wait_for_timeout(700)
                r["campo"] = pg.evaluate(JS_CAMPO, campo)
                if boton:
                    r["boton"] = pg.evaluate(JS_CAMPO, boton)
                if "dialog" in campo:
                    r["botonesDelDialogo"] = pg.evaluate("(()=>{const d=document.querySelector('dialog[open]');if(!d)return null;const b=[...d.querySelectorAll('button[type=submit], .lime-button')].pop();if(!b)return null;const q=b.getBoundingClientRect();const sc=[d,...d.querySelectorAll('*')].find(e=>['auto','scroll'].includes(getComputedStyle(e).overflowY)&&e.scrollHeight>e.clientHeight+1);return {bottom:Math.round(q.bottom),H:innerHeight,visibleSinScroll:q.bottom<=innerHeight,dialogoScrollable:!!sc,altoDialogo:Math.round(d.getBoundingClientRect().height)}})()")
                pg.screenshot(path=str(OUT / f"teclado_{H}_{re.sub(r'[^a-z0-9]+','-',nombre.lower())}.png"))
            except Exception as ex:
                r["error"] = str(ex)[:100].replace(chr(10), " ")
            res.append(r)
            print("teclado", H, nombre, "entero" if (r.get("campo") or {}).get("entero") else r.get("error", "NO entero"), flush=True)
            pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        ctx.close()
    volcar("teclado.json", res)


# ---------------------------------------------------------------- ZOOM / REFLOW
JS_ZOOM = r"""() => {
  const W = document.documentElement.clientWidth, H = innerHeight;
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const nombre = e => e.tagName.toLowerCase() + '.' + [...e.classList].slice(0, 2).join('.');
  const cn = e => (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className) + '';
  const scrollH = document.documentElement.scrollWidth - W;
  const clipeado = [...document.querySelectorAll('body *')].filter(e => { if (!vis(e)) return false; const s = getComputedStyle(e);
    if (!(['hidden', 'clip'].includes(s.overflowX) || ['hidden', 'clip'].includes(s.overflowY))) return false;
    if (!(e.innerText || '').trim()) return false; return e.scrollHeight > e.clientHeight + 2 || e.scrollWidth > e.clientWidth + 2; })
    .filter(e => !/topo|story|detail-land|hero-visual|scroll-progress|dot-grid|visually-hidden|skip/.test(cn(e))).slice(0, 12).map(e => nombre(e) + ' ' + e.clientWidth + 'x' + e.clientHeight + ' (contenido ' + e.scrollWidth + 'x' + e.scrollHeight + ')');
  const elipsis = [...document.querySelectorAll('body *')].filter(e => vis(e) && getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1).length;
  const fijos = [...document.querySelectorAll('body *')].filter(e => ['fixed', 'sticky'].includes(getComputedStyle(e).position) && vis(e)).map(e => ({ n: nombre(e), top: Math.round(e.getBoundingClientRect().top), h: Math.round(e.getBoundingClientRect().height), w: Math.round(e.getBoundingClientRect().width) })).filter(f => f.w > W * 0.5 && f.h > 20);
  const arriba = fijos.filter(f => f.top <= 1).reduce((a, f) => a + f.h, 0);
  const fuera = [...document.querySelectorAll('body *')].filter(e => { if (!vis(e)) return false; const r = e.getBoundingClientRect(); return r.right > W + 1 && !e.closest('.dashboard-sidebar-nav'); })
    .filter(e => !/topo|story|detail-land|circle/.test(cn(e)) && !/^(svg|path|circle)$/i.test(e.tagName)).slice(0, 6).map(e => nombre(e) + ' der=' + Math.round(e.getBoundingClientRect().right));
  const tams = [...document.querySelectorAll('body *')].filter(e => vis(e) && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => parseFloat(getComputedStyle(e).fontSize));
  return { W, H, scrollHorizontal: scrollH, elementosFuera: fuera, textoRecortado: clipeado, truncadosConElipsis: elipsis, fijosArriba: fijos.slice(0, 3), alturaFijaArribaPx: arriba, porcentajeVistaOcupadaPorFijos: Math.round(100 * arriba / H), fuenteMinima: tams.length ? Math.min(...tams) : null };
}"""


def parte_zoom(nav):
    res = {}
    esc = [("200% sobre 1440x900 (viewport CSS 720x450)", 720, 450, None),
           ("400% sobre 1280x1024 (reflow WCAG 1.4.10: 320x256)", 320, 256, None),
           ("texto al 200% en celular (375x812, html 32px)", 375, 812, "html{font-size:200% !important}")]
    ctx, pg = contexto(nav, 1440, 900)
    for ruta in rutas:
        if not ir(pg, ruta, 1200):
            continue
        alto = pg.evaluate("document.documentElement.scrollHeight"); y = 0
        while y < alto:
            pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(80); y += 450
        pg.evaluate("window.scrollTo(0,0)")
        clave = anon(ruta); res[clave] = {}
        for nombre, w, h, css in esc:
            pg.set_viewport_size({"width": w, "height": h})
            if css:
                pg.add_style_tag(content=css)
            pg.wait_for_timeout(700)
            pg.evaluate("window.scrollTo(0,0)")
            d = pg.evaluate(JS_ZOOM)
            res[clave][nombre] = d
            if (d["scrollHorizontal"] > 0 or d["porcentajeVistaOcupadaPorFijos"] >= 25) and w != 375:
                pg.screenshot(path=str(OUT / f"zoom_{re.sub(r'[^a-z0-9]+','-',clave.lower()).strip('-')}_{w}x{h}.png"))
            if css:
                pg.evaluate("document.querySelectorAll('style').forEach(s=>{if(s.textContent.includes('200% !important'))s.remove()})")
        pg.set_viewport_size({"width": 1440, "height": 900})
        print("zoom", clave[:44], {k[:6]: (v["scrollHorizontal"], v["porcentajeVistaOcupadaPorFijos"]) for k, v in res[clave].items()}, flush=True)
    volcar("zoom.json", res); ctx.close()


with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    {"foco": parte_foco, "dialogos": parte_dialogos, "carrusel": parte_carrusel, "teclado": parte_teclado, "zoom": parte_zoom}[PARTE](nav)
    nav.close()
print("fin", PARTE, "requests bloqueados:", len(BLOQUEADOS), flush=True)
