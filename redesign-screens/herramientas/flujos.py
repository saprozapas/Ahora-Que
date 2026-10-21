"""Recorrido funcional de los flujos criticos, CON escritura (datos de prueba).

Usa la sesion guardada (AQ_ESTADO) y crea todo con el prefijo "ZZ Sereno":
un grupo, una idea, un plan, una publicacion y una encuesta. Al final los
borra por la interfaz y deja el rastro de lo que no se pudo borrar.
No invita a nadie, no reacciona a contenido ajeno y no toca el perfil.

Uso: AQ_ESTADO=estado.json python flujos.py <base_url> <salida.json>
"""
import datetime, json, os, re, sys, time
from playwright.sync_api import sync_playwright

BASE, SALIDA = sys.argv[1], sys.argv[2]
ESTADO = os.environ["AQ_ESTADO"]
PREFIJO = "ZZ Sereno"
resultados, rastro = [], {}


def paso(nombre):
    def deco(f):
        def envoltura(*a, **k):
            t = time.time()
            try:
                extra = f(*a, **k)
                resultados.append({"paso": nombre, "ok": True, "seg": round(time.time() - t, 1), "detalle": extra})
                print("OK  ", nombre, extra or "", flush=True)
                return True
            except Exception as ex:
                resultados.append({"paso": nombre, "ok": False, "seg": round(time.time() - t, 1), "detalle": str(ex)[:300].replace("\n", " ")})
                print("FALLA", nombre, str(ex)[:160].replace("\n", " "), flush=True)
                return False
        return envoltura
    return deco


def esperar(pg, ms=900):
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(ms)


with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    ctx = nav.new_context(viewport={"width": 1440, "height": 900}, locale="es-UY", storage_state=ESTADO)
    pg = ctx.new_page()
    errores_js = []
    pg.on("pageerror", lambda e: errores_js.append(str(e)[:160]))
    pg.on("console", lambda m: errores_js.append("console: " + m.text[:140]) if m.type == "error" and "Failed to load resource" not in m.text else None)

    @paso("1. Sesion activa")
    def sesion():
        pg.goto(BASE + "/dashboard"); esperar(pg)
        assert "/login" not in pg.url, "sin sesion"
        return pg.title()
    if not sesion():
        json.dump(resultados, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1); sys.exit(2)

    @paso("2. Crear grupo")
    def crear_grupo():
        pg.goto(BASE + "/grupos/nuevo"); esperar(pg)
        pg.fill("#name", f"{PREFIJO} grupo")
        pg.fill("#description", "Grupo de prueba de la migracion a Sereno. Se borra solo.")
        pg.click("form button[type=submit]"); esperar(pg, 1500)
        m = re.search(r"/grupos/([0-9a-f-]{36})", pg.url)
        if not m:
            # bug conocido de main: puede quedar en la pantalla de creacion
            pg.goto(BASE + "/grupos"); esperar(pg)
            href = pg.evaluate("[...document.querySelectorAll('a[href^=\"/grupos/\"]')].find(a=>a.textContent.includes('ZZ Sereno'))?.getAttribute('href')")
            m = re.search(r"/grupos/([0-9a-f-]{36})", href or "")
            assert m, "no se encontro el grupo creado"
            rastro["nota_crear_grupo"] = "quedo en la pantalla de creacion (bug 8 de Bugs.md)"
        rastro["grupo_id"] = m.group(1)
        return "grupo creado"
    crear_grupo()
    G = rastro.get("grupo_id")

    @paso("3. Tablero vacio, cabecera y pestañas")
    def cabecera():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        assert pg.locator("h1").inner_text().startswith(PREFIJO)
        assert pg.locator(".tabs .tab").count() == 3
        assert pg.locator(".empty-state").count() == 1
        return "h1 + 3 pestañas + estado vacio"
    cabecera()

    @paso("4. Modal Invitar: abre, busca amigos y NO invita")
    def invitar():
        pg.click("[data-modal-open='modal-invitar']"); esperar(pg, 1500)
        assert pg.evaluate("document.activeElement.id") == "invitar-buscar", "el foco no fue al buscador"
        n = pg.locator("#invitar-lista .friend-result").count()
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        assert pg.evaluate("document.activeElement.getAttribute('data-modal-open')") == "modal-invitar", "el foco no volvio al boton"
        return f"{n} amigos listados; foco ok al abrir y al cerrar"
    invitar()

    @paso("5. Modal Editar grupo: foco al nombre, Escape")
    def editar():
        pg.click("[data-modal-open='modal-editar-grupo']"); pg.wait_for_timeout(400)
        assert pg.evaluate("document.activeElement.id") == "editar-nombre"
        titulos = pg.locator("#modal-editar-grupo .cosmetic-choice").count()
        marco = pg.input_value("#modal-editar-grupo input[name=marco_semanas]")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        return f"{titulos} opciones de titulo; marco conservado='{marco}'"
    editar()

    @paso("6. Chat de grupo: enviar y ver la burbuja")
    def chat():
        pg.goto(f"{BASE}/grupos/{G}/chat"); esperar(pg)
        pg.fill("#group-chat-input", "hola, prueba de Sereno"); pg.click("#group-chat-send"); esperar(pg, 1500)
        assert pg.locator(".chat-message.is-own .chat-bubble").count() >= 1, "no aparecio la burbuja propia"
        bg = pg.evaluate("getComputedStyle(document.querySelector('.chat-message.is-own .chat-bubble')).backgroundColor")
        return f"burbuja propia {bg}"
    chat()

    @paso("7. Crear idea (con un lugar)")
    def idea():
        pg.goto(BASE + "/planes/nueva-idea"); esperar(pg)
        pg.fill("#nombre", f"{PREFIJO} idea"); pg.fill("#descripcion", "Idea de prueba")
        pg.fill("#busqueda-texto", "cafe"); pg.click("#boton-buscar"); esperar(pg, 2000)
        n = pg.locator("#resultados .planner-result").count()
        if n:
            pg.locator("#resultados .planner-result button").first.click(); pg.wait_for_timeout(400)
            assert pg.locator("#lista-elegidos li").count() == 1
        pg.click("#form-plan button[type=submit]"); esperar(pg, 1500)
        return f"{n} resultados de busqueda; guardada"
    idea()

    @paso("8. Postular la idea al grupo")
    def postular():
        pg.goto(f"{BASE}/grupos/{G}/postular"); esperar(pg)
        radio = pg.locator("input[name=idea_id]")
        hubo = None
        for i in range(radio.count()):
            txt = radio.nth(i).locator("xpath=..").inner_text()
            if PREFIJO in txt:
                radio.nth(i).check(force=True); hubo = True; break
        assert hubo, "la idea de prueba no aparece"
        fecha = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        pg.fill("#postular-fecha", fecha); pg.fill("#postular-hora", "20:30")
        pg.click("form.postular button[type=submit]"); esperar(pg, 1500)
        assert "En votación" in pg.content() or pg.locator("#tablero-votacion").count(), "el plan no quedo en votacion"
        return "plan en votacion"
    postular()

    @paso("9. Votar (Sí / Sí)")
    def votar():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        art = pg.locator("#tablero-votacion").locator("xpath=ancestor::section").locator("article.board-plan").first
        art.locator("input[name=me_gusta][value=si]").check(force=True)
        art.locator("input[name=puedo][value=si]").check(force=True)
        art.locator("button[type=submit]").first.click(); esperar(pg, 1500)
        art = pg.locator("article.board-plan").first
        return "voto enviado: " + (pg.locator("article.board-plan .board-plan__count").first.inner_text()[:60] if pg.locator("article.board-plan .board-plan__count").count() else "")
    votar()

    @paso("10. Cerrar votacion: dialogo de confirmacion propio")
    def cerrar():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        pg.locator("form[data-confirmar] button").first.click(); pg.wait_for_timeout(500)
        d = pg.evaluate("(()=>{const d=document.querySelector('dialog[open]');return d?{foco:document.activeElement.innerText.trim(),texto:d.querySelector('p').innerText}:null})()")
        assert d, "no se abrio el dialogo propio (confirm nativo?)"
        assert d["foco"] == "Cancelar", "el foco inicial no esta en Cancelar"
        pg.click("dialog[open] button[value=si]"); esperar(pg, 2000)
        return f"dialogo ok, foco inicial en {d['foco']}"
    cerrar()

    @paso("11. Estado del plan tras cerrar la votacion")
    def estado():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        secciones = pg.evaluate("[...document.querySelectorAll('.board__head h2')].map(h=>h.innerText)")
        rastro["secciones_tras_cerrar"] = secciones
        return str(secciones)
    estado()

    @paso("12. Proponer horario, votarlo y cerrarlo (si el plan busca horario)")
    def horario():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        if not pg.locator("#tablero-horario").count():
            return "no aplica (el plan no quedo esperando horario)"
        fecha = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()
        pg.fill("input[name=fecha]", fecha); pg.fill("input[name=hora]", "19:00")
        pg.locator("form.board-plan__new-slot button[type=submit]").click(); esperar(pg, 1500)
        pg.locator(".board-slots__vote button[value=si]").first.click(); esperar(pg, 1500)
        pg.locator(".board-slots form[data-confirmar] button").first.click(); pg.wait_for_timeout(500)
        pg.click("dialog[open] button[value=si]"); esperar(pg, 2000)
        return "horario propuesto, votado y cerrado"
    horario()

    @paso("13. Racha y detalle del plan")
    def racha():
        pg.goto(f"{BASE}/racha/{G}"); esperar(pg)
        assert pg.locator("h1").count() == 1
        pg.locator("button.racha-hito").first.click(); pg.wait_for_timeout(400)
        ok = pg.evaluate("!!document.querySelector('dialog[open]')")
        pg.keyboard.press("Escape")
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        href = pg.evaluate("document.querySelector('article.board-plan h3 a')?.getAttribute('href')")
        if href:
            rastro["plan_href"] = href
            pg.goto(BASE + href); esperar(pg)
        return f"racha ok (hito abre dialogo={ok}); plan {href}"
    racha()

    @paso("14. Social: publicar el plan, me gusta, comentar, guardar")
    def social():
        pg.goto(BASE + "/social?tab=amigos"); esperar(pg, 2500)
        pg.click("[data-modal-open='soc-modal-publicar']"); esperar(pg, 1500)
        radios = pg.locator("#soc-modal-publicar input[name=plan_id]")
        sel = None
        for i in range(radios.count()):
            if PREFIJO in radios.nth(i).locator("xpath=ancestor::label").inner_text():
                radios.nth(i).check(force=True); sel = True; break
        assert sel, "el plan de prueba no aparece entre los publicables"
        pg.fill("#soc-publicar-texto", "Publicacion de prueba de Sereno (se borra)")
        pg.click("[data-soc-publicar-enviar]"); esperar(pg, 2500)
        tarjeta = pg.locator(".soc-tarjeta", has_text=PREFIJO).first
        assert tarjeta.count(), "no aparecio la tarjeta publicada"
        tarjeta.locator("[data-soc-like]").click(); pg.wait_for_timeout(800)
        tarjeta.locator("[data-soc-guardar]").click(); pg.wait_for_timeout(800)
        tarjeta.locator("[data-soc-comentarios]").click(); pg.wait_for_timeout(600)
        pg.locator(".soc-tarjeta", has_text=PREFIJO).first.locator("[data-soc-comentario-input]").fill("comentario de prueba")
        pg.keyboard.press("Enter"); pg.wait_for_timeout(1500)
        like = tarjeta.locator("[data-soc-like]").get_attribute("aria-pressed")
        return f"publicada; like aria-pressed={like}"
    social()

    @paso("15. Encuesta del grupo: crear, responder y cancelar")
    def encuesta():
        pg.goto(f"{BASE}/grupos/{G}/encuestas/nueva"); esperar(pg)
        pg.fill("#titulo", f"{PREFIJO} encuesta"); pg.click("form button[type=submit]"); esperar(pg, 2000)
        assert pg.locator("#encuestas-grupo").count(), "no aparece la encuesta en el grupo"
        fecha = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        pg.fill("input[name=disp_fecha] >> nth=0", fecha); pg.fill("input[name=disp_desde] >> nth=0", "18:00"); pg.fill("input[name=disp_hasta] >> nth=0", "22:00")
        pg.locator("#encuestas-grupo .encuesta-form button[type=submit]").click(); esperar(pg, 2000)
        pg.locator("#encuestas-grupo .encuesta-acciones form >> nth=1").locator("button").click(); esperar(pg, 2000)
        return "encuesta creada, respondida y cancelada"
    encuesta()

    @paso("16. Asistente de IA: panel carga el historial (sin enviar mensajes)")
    def asistente():
        pg.goto(f"{BASE}/grupos/{G}/asistente"); esperar(pg, 1500)
        assert pg.locator("#chatbot-form").count() == 1
        return "panel ok"
    asistente()

    # ------------------------------------------------------------------ limpieza
    @paso("17. Limpieza: borrar la publicacion")
    def borrar_pub():
        pg.goto(BASE + "/social?tab=amigos"); esperar(pg, 2500)
        t = pg.locator(".soc-tarjeta", has_text=PREFIJO).first
        t.locator("[data-soc-eliminar]").click(); pg.wait_for_timeout(500)
        pg.click("dialog[open] button[value=si]"); esperar(pg, 2000)
        assert pg.locator(".soc-tarjeta", has_text=PREFIJO).count() == 0
        return "publicacion borrada"
    borrar_pub()

    @paso("18. Limpieza: borrar el plan (Eliminar plan, dialogo propio)")
    def borrar_plan():
        href = rastro.get("plan_href")
        assert href, "no hay plan"
        pg.goto(BASE + href); esperar(pg)
        pg.locator("form[data-confirmar] button", has_text="Eliminar").click(); pg.wait_for_timeout(500)
        pg.click("dialog[open] button[value=si]"); esperar(pg, 2000)
        return "plan eliminado"
    borrar_plan()

    @paso("19. Limpieza: borrar la idea guardada")
    def borrar_idea():
        pg.goto(BASE + "/planes/guardados"); esperar(pg)
        n = pg.locator("article, li", has_text=PREFIJO).count()
        if not n:
            return "no habia idea suelta"
        pg.locator("form[data-confirmar] button", has_text="Quitar").first.click(); pg.wait_for_timeout(500)
        pg.click("dialog[open] button[value=si]"); esperar(pg, 2000)
        return "idea quitada de guardados"
    borrar_idea()

    @paso("20. Limpieza: abandonar el grupo de prueba")
    def abandonar():
        pg.goto(f"{BASE}/grupos/{G}"); esperar(pg)
        pg.click("[data-modal-open='modal-abandonar-grupo']"); pg.wait_for_timeout(400)
        pg.click("#modal-abandonar-grupo button[type=submit]"); esperar(pg, 2000)
        return "grupo abandonado (la fila del grupo y sus mensajes quedan: se borran por SQL)"
    abandonar()

    rastro["errores_js"] = errores_js[:12]
    json.dump({"resultados": resultados, "rastro": rastro}, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nav.close()
print("fin: ok", sum(r["ok"] for r in resultados), "de", len(resultados))
