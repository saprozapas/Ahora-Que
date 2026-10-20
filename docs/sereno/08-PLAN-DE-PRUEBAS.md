# 08 — Plan de pruebas de regresión y cómo repetir las mediciones

## 1. Herramientas (todas ya probadas en esta auditoría)

| Herramienta | Qué hace | Dónde está hoy |
|---|---|---|
| `medir.py <url> <carpeta> <rutas> ` | Por ruta × viewport × tema guarda un JSON con desborde, objetivos táctiles <44, histogramas de fuentes/radios/gaps/alturas de botón, texto <12 px, asimetría, **contraste WCAG por nodo**, a11y (h1, saltos de título, `img` sin `alt`/tamaño, botones sin nombre, inputs sin etiqueta, elementos fixed/sticky), fuentes cargadas. Baja la página de a medio viewport para disparar los `scroll-reveal`. Variable `VPS="320x640,375x812,…"` para elegir viewports. | `redesign-screens/audit/herramientas/medir.py` (copiado desde el scratchpad de la sesión; falta versionarlo). |
| `reverificar.py <carpeta>` | Re-mide hallazgos puntuales (R1…R11) | `redesign-screens/audit/herramientas/reverificar.py` |
| `redesign-screens/capturar.py` | Capturas `antes` / `despues`, 375 y 1440, `--tema noche`, con login por variables de entorno `AQ_USUARIO`/`AQ_CLAVE` | rama `redesign-sereno` |
| `redesign-screens/preview.py` | App con datos de ejemplo en memoria (puerto 5058); solo para la rama, no sirve para las pantallas nuevas de `main` | rama |

Notas de uso para no repetir tropiezos:
- En Git Bash, un argumento `/` se convierte en `C:/Program Files/Git/`: usar `MSYS_NO_PATHCONV=1`.
- No usar `python -I` con Playwright (queda fuera de su `site-packages`).
- Poner `PYTHONDONTWRITEBYTECODE=1` para no ensuciar `git status` con `.pyc` versionados.
- Levantar `main` sin recarga ni debug: `python -c "from app import app; app.run(port=5099, use_reloader=False, threaded=True)"`. `app.py` es de un solo hilo con `debug=True` (el reloader duplica el proceso).
- Una corrida completa de 6 rutas × 8 viewports × 2 temas tarda unos 3-4 minutos por ruta con scroll; para la rama (4 viewports) ~1 minuto por ruta.
- Las capturas a página completa salen en blanco si no se dispara `scroll-reveal` (pasaba en la landing de `main`); `medir.py` ya lo resuelve.

### Interacción, teclado y zoom (herramienta nueva)

`redesign-screens/audit/herramientas/interaccion_sesion.py <url> <salida> <parte>` con `parte` = `foco` | `dialogos` | `carrusel` | `teclado` | `zoom`. **Bloquea en el navegador todo request que no sea GET** (salvo el login), así que se puede correr contra la base real sin riesgo de escribir. Credenciales por `AQ_USUARIO`/`AQ_CLAVE`. Pitfalls: esperar ~280 ms después de cada `Tab` antes de leer estilos (transición de foco), y no contar como inalcanzables los ítems de `<details>` cerrados. El teclado en pantalla se aproxima achicando la altura de la vista; para el real hace falta un dispositivo.

## 2. Matriz de regresión

Eje | Valores
---|---
Pantallas | las 33 rutas HTML de `01-INVENTARIO-PANTALLAS.md`
Viewports | 320×640, 375×812, 414×896, 768×1024, 1024×768, 1280×800, 1440×900, 1920×1080
Tema | claro, noche
Estados | (los que apliquen; ver lista de abajo)

Estados mínimos por pantalla para la etapa con sesión (cada uno con captura y medición):

| Pantalla | Estados |
|---|---|
| Grupo | sin planes · 1 plan por estado (idea, votación, buscando horario, confirmado, para puntuar, archivado) · grupo de 1 persona y de muchas · encuesta abierta y eligiendo · admin y no admin · cada modal abierto |
| Chat | vacío · con ≥ 30 mensajes (scroll) · mensaje de 500 caracteres sin espacios · nombre con emoji · teclado en pantalla (celular) |
| Social | vacío · 1 publicación sin foto · con 1 y con 2 fotos (cuadrada y vertical) · hilo de comentarios abierto · carrusel en la 2.ª foto · diálogo de compartir (con y sin fotos) · error del feed |
| Inbox | sin nada · solo solicitudes · solo avisos · ambos |
| Moderación | sin reportes · con reporte con foto · con reporte eliminado |
| Racha | inactiva · activa · hito logrado · título y marco puestos |
| Formularios | vacío · error por campo · éxito |
| Todas | texto largo, tildes y emojis en nombre de grupo y de plan; 200 % de zoom; `prefers-reduced-motion: reduce` |

Interacción a recorrer manualmente (no se automatizó en esta auditoría): `Tab` completo con foco visible, `Esc` en cada diálogo (y devolución del foco al disparador), `:hover`, `:active`, deshabilitado, carrusel con teclado, trampa de foco.

## 3. Criterios de comparación

1. **Sin regresión visible**: capturas antes/después (`capturar.py antes` sobre `main` vs `despues` sobre la rama) lado a lado; los cambios esperados son de paleta, tipografía y radios, no de contenido ni orden.
2. **Sin regresión medible**: `medir.py` antes y después; para cada ruta/viewport/tema, ningún indicador empeora: scroll horizontal = 0, táctiles <44 y fallos de contraste no suben, texto <12 px no sube.
3. **Metas absolutas** de la tabla global de `06-PLAN-DE-MIGRACION.md`.
4. **Consola limpia**: `read_console_messages` sin errores; `read_network_requests` sin 404 de CSS/JS/fuentes.

Línea base ya medida (referencia para comparar): páginas públicas de `main` (`redesign-screens/audit/<ruta>/`) y las 14 pantallas de la rama (`redesign-screens/audit/sereno-rama/<ruta>/`). Resumen de esa línea base: `main` público → 0 desbordes, 0 fallos reales de contraste, táctiles <44: landing 3, login 1, registro 1; rama → 13 a 37 táctiles <44 y 2 a 38 fallos de contraste por pantalla a 375 px (ver `02-HALLAZGOS.md`).

## 4. Los 10 flujos críticos (recorrido funcional)

Para cada uno: resultado esperado y qué verificar que **no se rompió** con el rediseño (envío de formularios, `name`/`value`, ganchos JS, diálogos).

| # | Flujo | Pasos | Verificar |
|--:|---|---|---|
| 1 | Registro y login | `/register` → cuenta nueva → `/login` → `/dashboard` → `/logout` | errores por campo, mensajes, redirecciones |
| 2 | Crear grupo | `/grupos/nuevo` → crear → aterriza en el grupo (bug 8 de `Bugs.md`: "te deja en la página de creación") | redirección correcta |
| 3 | Invitar | en el grupo: "Invitar" (modal) → buscar usuarios/amigos (bug 5: no aparecían) → invitar; el invitado acepta en `/inbox` | buscador del modal, `onclick…close()`, contador del Inbox |
| 4 | Postular una idea | crear idea (`/planes/nueva-idea`, con y sin asistente) → `/grupos/<id>/postular` | lista de lugares elegidos (JS inline), `chatbot.js` |
| 5 | Votar | votar plan (me gusta / puedo) → votar horario → proponer horario | formularios del tablero, `is-elegido` |
| 6 | Confirmar | cerrar votación (`data-confirmar`) → plan pasa a confirmado → "Me sumo" / bajarme | diálogo `preguntar` (no `confirm()` nativo: C-14) |
| 7 | Puntuar | plan archivado → puntaje 1-5 | el control de estrellas envía el valor |
| 8 | Publicar en Social | `/social` → "Compartir un plan" (con 0, 1 y 2 fotos) → aparece en el feed | previas de fotos, carrusel, límites |
| 9 | Me gusta, comentar, guardar, reportar | sobre una publicación ajena | `aria-pressed`, contadores, hilo, diálogo de reporte |
| 10 | Inbox | aceptar/rechazar invitación y solicitud; avisos de publicaciones se marcan como leídos al abrir | contador de la barra lateral baja al instante (`_borrar_inbox_guardado`) |

Extras que ya dieron problemas en la historia del proyecto (`Bugs.md`): salir de un grupo con plan en curso (bug 11), planes que pasan a archivados al entrar al grupo (bug 14), planes pasados en el calendario (bug 16).

**Reglas de seguridad para probar sobre la base compartida** (Supabase): usar usuarios "(demo)"; los flujos 1-10 escriben datos reales, así que correrlos solo contra una cuenta de prueba y limpiar con `scripts/datos_demo_social.py borrar` lo que corresponda. Antes de cualquier prueba que escriba, confirmar con Santi (ver la memoria del proyecto: DDL o datos en la base compartida solo con confirmación).

## 5. Pruebas de la fusión (Fase 1)

`grep -rn '^<<<<<<<\|^>>>>>>>' templates static` sin resultados · una sola carga de `app.js` por página · `window.preguntar` abre en 4 lugares · `data-confirmar` presente en `plan_detalle` y `planes_lista` · sidebar reordenable (arrastrar) funciona · noche en pantalla heredada y nueva.

## 6. Cuándo se considera "hecha" una fase

Criterios de aceptación de la fase cumplidos **con números de `medir.py` pegados en el tablero de avance** (no "se ve bien"), capturas en `redesign-screens/despues/<fase>/`, flujos críticos que toquen esa fase en verde, y commit con el mensaje de la fase.
