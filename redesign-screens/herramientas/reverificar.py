import json, pathlib, sys
from playwright.sync_api import sync_playwright

MAIN = "http://127.0.0.1:5099"
RAMA = "http://127.0.0.1:5058"
OUT = pathlib.Path(sys.argv[1])

LUM = """
const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return {r:p[0],g:p[1],b:p[2],a:p[3]===undefined?1:p[3]}; };
const lum = ({r,g,b}) => { const f = v => { v/=255; return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055,2.4); }; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
const mez = (f,b) => ({r:f.r*f.a+b.r*(1-f.a), g:f.g*f.a+b.g*(1-f.a), b:f.b*f.a+b.b*(1-f.a), a:1});
const fondo = e => { let n=e, capas=[]; while(n&&n.nodeType===1){ const c=parse(getComputedStyle(n).backgroundColor); if(c.a>0){capas.push(c); if(c.a>=1)break;} n=n.parentElement;} let base={r:255,g:255,b:255,a:1}; for(let i=capas.length-1;i>=0;i--) base=mez(capas[i],base); return base; };
const ratio = e => { const bg=fondo(e); const fg=mez(parse(getComputedStyle(e).color),bg); const a=lum(fg), b=lum(bg); return Math.round((Math.max(a,b)+.05)/(Math.min(a,b)+.05)*100)/100; };
"""

def abrir(nav, base, ruta, w, h, tema="claro"):
    ctx = nav.new_context(viewport={"width": w, "height": h}, locale="es-UY")
    if tema == "noche":
        ctx.add_init_script("try{localStorage.setItem('ahoraque-theme','night')}catch(e){}")
    pg = ctx.new_page()
    pg.goto(base + ruta, wait_until="networkidle", timeout=30000)
    y = 0
    alto = pg.evaluate("document.documentElement.scrollHeight")
    while y < alto:
        pg.evaluate(f"window.scrollTo(0,{y})"); pg.wait_for_timeout(100); y += h // 2
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(700)
    return ctx, pg

res = {}
with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    # main, landing 375
    ctx, pg = abrir(nav, MAIN, "/", 375, 812)
    res["R1 H-001 enlaces .pillar-cards a (alto px)"] = pg.evaluate("[...document.querySelectorAll('.pillar-cards a')].map(e=>Math.round(e.getBoundingClientRect().height))")
    res["R2 H-002 .decision-meta font-size @375"] = pg.evaluate("getComputedStyle(document.querySelector('.decision-meta')).fontSize")
    res["R3 H-003 tamanos de fuente distintos @375"] = pg.evaluate("new Set([...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().width&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).map(e=>getComputedStyle(e).fontSize)).size")
    res["R4 H-004 img sin width/height"] = pg.evaluate("[...document.querySelectorAll('img')].filter(i=>!(i.getAttribute('width')&&i.getAttribute('height'))).map(i=>i.className)")
    res["R4b scroll horizontal real @375"] = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ctx.close()
    ctx, pg = abrir(nav, MAIN, "/", 1440, 900)
    res["R2b .decision-meta @1440"] = pg.evaluate("getComputedStyle(document.querySelector('.decision-meta')).fontSize")
    res["R1b enlaces .pillar-cards a @1440"] = pg.evaluate("[...document.querySelectorAll('.pillar-cards a')].map(e=>Math.round(e.getBoundingClientRect().height))")
    ctx.close()
    # rama Sereno
    ctx, pg = abrir(nav, RAMA, "/dashboard", 1440, 900)
    res["R5 H-S01 p.voice ratio (ink-3 sobre papel)"] = pg.evaluate("(()=>{"+LUM+"return ratio(document.querySelector('.dash-brief .voice'))})()")
    res["R5b h1 en /dashboard"] = pg.evaluate("document.querySelectorAll('h1').length")
    res["R11 H-S08 .dash-shortcuts: alto de cada card / ancho contenedor / ancho tarjetas"] = pg.evaluate("(()=>{const c=document.querySelector('.dash-shortcuts'); const k=[...c.children]; return {altos:k.map(e=>Math.round(e.getBoundingClientRect().height)), contenedor:Math.round(c.getBoundingClientRect().width), anchos:k.map(e=>Math.round(e.getBoundingClientRect().width)), gridCols:getComputedStyle(c).gridTemplateColumns, alignItems:getComputedStyle(c).alignItems}})()")
    ctx.close()
    ctx, pg = abrir(nav, RAMA, "/dashboard", 375, 812)
    res["R6 H-S02 .meta ratios min"] = pg.evaluate("(()=>{"+LUM+"const r=[...document.querySelectorAll('.meta')].filter(e=>e.getBoundingClientRect().width).map(ratio); return {n:r.length,min:Math.min(...r),max:Math.max(...r)}})()")
    res["R7 H-S03 .icon-btn tamanos"] = pg.evaluate("[...document.querySelectorAll('.icon-btn')].map(e=>Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height))")
    res["R7b sidebar links alto"] = pg.evaluate("[...document.querySelectorAll('.dashboard-sidebar-link')].map(e=>Math.round(e.getBoundingClientRect().height))")
    res["R8 H-S04 badge font-size"] = pg.evaluate("[...document.querySelectorAll('.badge')].map(e=>getComputedStyle(e).fontSize)")
    res["R9 H-S05 sidebar nav: scrollWidth/clientWidth y enlaces fuera de viewport"] = pg.evaluate("(()=>{const n=document.querySelector('.dashboard-sidebar-nav'); const W=document.documentElement.clientWidth; const l=[...n.querySelectorAll('a')]; return {scrollW:n.scrollWidth, clientW:n.clientWidth, overflowX:getComputedStyle(n).overflowX, total:l.length, fuera:l.filter(e=>e.getBoundingClientRect().left>=W||e.getBoundingClientRect().right>W).map(e=>e.innerText.trim().split('\\n')[0])}})()")
    ctx.close()
    ctx, pg = abrir(nav, RAMA, "/grupos/g1", 375, 812)
    res["R8b avatar font-size en /grupos/g1"] = pg.evaluate("[...new Set([...document.querySelectorAll('.avatar')].map(e=>getComputedStyle(e).fontSize+' en '+Math.round(e.getBoundingClientRect().width)+'px'))]")
    res["R10 H-S07 enlaces sin nombre accesible /grupos/g1"] = pg.evaluate("[...document.querySelectorAll('a.idea-menu__item')].map(e=>({txt:(e.innerText||'').trim().slice(0,30), aria:e.getAttribute('aria-label')}))")
    ctx.close()
    nav.close()

(OUT / "reverificacion.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
