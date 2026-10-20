"""Medicion automatica (Fase C) sobre paginas publicas de main. Solo lectura.

Uso: python -I medir.py <base_url> <carpeta_salida> <ruta1,ruta2,...> [--sesion]
Guarda JSON crudo por pantalla/viewport/tema y capturas a 375 y 1440.
"""
import json, re, sys, pathlib
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = pathlib.Path(sys.argv[2])
RUTAS = sys.argv[3].split(",")
VIEWPORTS = [(320, 640), (375, 812), (414, 896), (768, 1024), (1024, 768), (1280, 800), (1440, 900), (1920, 1080)]
TEMAS = ["claro", "noche"]
import os
if os.environ.get("VPS"):
    VIEWPORTS = [tuple(int(n) for n in v.split("x")) for v in os.environ["VPS"].split(",")]

JS = r"""
() => {
  const W = document.documentElement.clientWidth;
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const nombre = e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + [...e.classList].map(c => '.' + c).join('').slice(0, 60);
  const out = {};
  out.scrollW = document.documentElement.scrollWidth; out.clientW = W;
  out.scrollH = document.documentElement.scrollHeight;
  // 1 desborde
  out.fuera = [...document.querySelectorAll('body *')].filter(e => { if (!vis(e)) return false; const r = e.getBoundingClientRect();
      return (r.right > W + 1 || r.left < -1); }).slice(0, 25).map(e => nombre(e) + ' der=' + Math.round(e.getBoundingClientRect().right) + ' izq=' + Math.round(e.getBoundingClientRect().left));
  // 2 objetivos tactiles
  out.tactiles = [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button],summary')]
    .filter(e => vis(e)).map(e => ({ e, r: e.getBoundingClientRect() })).filter(({ r }) => r.width < 44 || r.height < 44)
    .map(({ e, r }) => nombre(e) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' "' + (e.innerText || e.getAttribute('aria-label') || e.value || '').trim().slice(0, 24) + '"');
  // 3 histogramas
  const h = { fontSize: {}, radio: {}, gap: {}, alturaBoton: {}, familia: {}, peso: {} };
  const suma = (o, k) => o[k] = (o[k] || 0) + 1;
  document.querySelectorAll('body *').forEach(e => { if (!vis(e)) return; const s = getComputedStyle(e);
    const tieneTexto = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (tieneTexto) { suma(h.fontSize, s.fontSize); suma(h.familia, s.fontFamily.split(',')[0].replace(/["']/g, '')); suma(h.peso, s.fontWeight); }
    if (s.borderRadius !== '0px') suma(h.radio, s.borderRadius);
    if (s.gap !== 'normal') suma(h.gap, s.gap);
    if (e.matches('button,[class*=button],[class*=btn],input[type=submit],a[class*=action]')) suma(h.alturaBoton, Math.round(e.getBoundingClientRect().height)); });
  out.hist = h;
  // 4 texto chico / interlineado
  out.textoChico = [...document.querySelectorAll('body *')].filter(e => vis(e) && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()))
    .map(e => ({ e, s: getComputedStyle(e) })).filter(({ s }) => parseFloat(s.fontSize) < 12)
    .slice(0, 25).map(({ e, s }) => nombre(e) + ' ' + s.fontSize + '/' + s.lineHeight);
  // 5 asimetria
  out.asimetria = [...document.querySelectorAll('main section, main form, main article, .section-shell')]
    .filter(e => vis(e)).map(e => ({ e, r: e.getBoundingClientRect() })).filter(({ r }) => r.width > 200 && r.width < W - 8 && Math.abs(r.left - (W - r.right)) > 2 && r.left > 4)
    .slice(0, 25).map(({ e, r }) => nombre(e) + ' izq=' + Math.round(r.left) + ' der=' + Math.round(W - r.right));
  // 6 contraste
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p[3] === undefined ? 1 : p[3] }; };
  const lum = ({ r, g, b }) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const mezcla = (f, b) => ({ r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1 });
  const fondoEfectivo = e => { let capas = []; let n = e; let indet = false;
    while (n && n.nodeType === 1) { const s = getComputedStyle(n); if (s.backgroundImage !== 'none') indet = true;
      const c = parse(s.backgroundColor); if (c && c.a > 0) { capas.push(c); if (c.a >= 1) break; } n = n.parentElement; }
    let base = { r: 255, g: 255, b: 255, a: 1 }; if (!capas.length || capas[capas.length - 1].a < 1) { const bc = parse(getComputedStyle(document.body).backgroundColor); if (bc && bc.a > 0) base = bc; }
    for (let i = capas.length - 1; i >= 0; i--) base = mezcla(capas[i], base); return { c: base, indet }; };
  const fallos = []; let evaluados = 0;
  document.querySelectorAll('body *').forEach(e => { if (!vis(e)) return; if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const s = getComputedStyle(e); if (parseFloat(s.opacity) < 1) { }
    const fg0 = parse(s.color); if (!fg0) return; const { c: bg, indet } = fondoEfectivo(e); const fg = mezcla(fg0, bg);
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(s.fontSize); const grande = px >= 24 || (px >= 18.66 && parseInt(s.fontWeight) >= 700); const min = grande ? 3 : 4.5; evaluados++;
    if (ratio < min) fallos.push({ el: nombre(e), ratio: Math.round(ratio * 100) / 100, min, fs: s.fontSize, txt: (e.innerText || '').trim().slice(0, 28), indeterminado: indet }); });
  out.contraste = { evaluados, fallos: fallos.slice(0, 60), totalFallos: fallos.length };
  // a11y
  out.a11y = {
    h1: document.querySelectorAll('h1').length,
    saltosTitulos: (() => { const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map(x => +x.tagName[1]); const s = []; for (let i = 1; i < hs.length; i++) if (hs[i] - hs[i - 1] > 1) s.push('h' + hs[i - 1] + '->h' + hs[i]); return s; })(),
    imgSinAlt: [...document.querySelectorAll('img:not([alt])')].map(nombre),
    imgSinTam: [...document.querySelectorAll('img')].filter(i => !(i.getAttribute('width') && i.getAttribute('height'))).length,
    botonesSinNombre: [...document.querySelectorAll('button,a[href],[role=button]')].filter(vis).filter(e => !(e.innerText || '').trim() && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby') && !e.getAttribute('title')).map(nombre),
    inputsSinEtiqueta: [...document.querySelectorAll('input:not([type=hidden]):not([type=submit]),select,textarea')].filter(vis).filter(e => !e.labels?.length && !e.getAttribute('aria-label') && !e.getAttribute('aria-labelledby')).map(nombre),
    fixedSticky: [...document.querySelectorAll('body *')].filter(e => ['fixed', 'sticky'].includes(getComputedStyle(e).position) && vis(e)).map(e => nombre(e) + ' ' + getComputedStyle(e).position + ' alto=' + Math.round(e.getBoundingClientRect().height)),
  };
  out.fuentes = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight);
  return out;
}
"""

def slug(ruta):
    return re.sub(r"[^a-z0-9]+", "-", ruta.lower()).strip("-") or "inicio"

with sync_playwright() as p:
    try:
        nav = p.chromium.launch(channel="msedge")
    except Exception:
        nav = p.chromium.launch()
    for ruta in RUTAS:
        for tema in TEMAS:
            for (w, hgt) in VIEWPORTS:
                ctx = nav.new_context(viewport={"width": w, "height": hgt}, locale="es-UY")
                if tema == "noche":
                    ctx.add_init_script("try{localStorage.setItem('ahoraque-theme','night')}catch(e){}")
                pg = ctx.new_page()
                try:
                    pg.goto(BASE + ruta, wait_until="networkidle", timeout=30000)
                except Exception as ex:
                    print("ERR goto", ruta, ex)
                pg.wait_for_timeout(600)
                # Dispara los scroll-reveal: baja de a un viewport y vuelve arriba.
                alto = pg.evaluate("document.documentElement.scrollHeight")
                y = 0
                while y < alto:
                    pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(120); y += hgt // 2
                pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(900)
                datos = pg.evaluate(JS)
                datos["ruta"] = ruta; datos["viewport"] = f"{w}x{hgt}"; datos["tema"] = tema
                datos["themeAttr"] = pg.evaluate("document.documentElement.dataset.theme || 'claro'")
                carpeta = OUT / slug(ruta); carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / f"medicion__{w}__{tema}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
                if w in (375, 1440):
                    pg.screenshot(path=str(carpeta / f"carga__{w}__{tema}.png"), full_page=True)
                ctx.close()
        print("ok", ruta, flush=True)
    nav.close()
