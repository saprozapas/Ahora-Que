# 01 — Inventario de pantallas, parciales, diálogos y matriz de cobertura

Rutas extraídas con un análisis del código (AST de `app.py` y `routes/*.py`, `main` commit `c373acc`). Estados deducidos de los `{% if %}` de cada template. "Sesión" = la ruta redirige a `/login` si no hay `user_id`.

Cobertura: **M-pub** = medida en `main` sin sesión (6 rutas); **M-ses** = medida en `main` con una cuenta de ejemplo real (375 y 1440 px, claro y noche); **M-rama** = medida en la rama Sereno con datos de ejemplo (la pantalla heredada rediseñada, no la versión de `main`); **—** = no medida.

---

## 1. Rutas que devuelven HTML (33)

| # | Ruta | Template | Blueprint / archivo | Sesión | Estados que puede mostrar | Cobertura |
|--:|---|---|---|:-:|---|---|
| 1 | `/` | `home.html` | `app.py` | no | landing (sin sesión) | **M-pub** · M-rama |
| 2 | `/dashboard` | `home.html` (modo `dashboard`) | `app.py` | sí | con/sin invitaciones pendientes | **M-ses** · M-rama |
| 3 | `/social` | `social.html` | `app.py` | sí | pestañas amigos/descubrir (feed por JS), actividad (niveles 4…todos), moderador sí/no, vacío, cargando, error | **M-ses** · M-rama (versión vieja: solo "Actividad") |
| 4 | `/explorar` | `explorar.html` | `app.py` | no | lista de 3 planes de ejemplo | **M-pub** |
| 5 | `/plan/<slug>` | `plan.html` | `app.py` | no | slug válido / cae al primero | **M-pub** |
| 6 | `/producto/<id>` | `plan.html` | `app.py` | no | igual que 5 | — (mismo template que 5) |
| 7 | `/contacto` | `contacto.html` | `app.py` | no | formulario / enviado | **M-pub** (estado "enviado" no) |
| 8 | `/login` | `login.html` | `auth.py` | no | con/sin mensaje de error | **M-pub** · M-rama |
| 9 | `/register` | `register.html` | `auth.py` | no | formulario, error, éxito | **M-pub** |
| 10 | `/calendario` | `calendario.html` | `calendario.py` | sí | mes con/sin planes, día actual | **M-ses** · M-rama |
| 11 | `/amigos` | `amigos.html` | `friends.py` | sí | con/sin amigos, buscar, modal invitar a grupo | **M-ses** · M-rama |
| 12 | `/grupos` | `grupos.html` | `group_auth.py` | sí | sin grupos (landing de grupos), con grupos, racha/marco, paginación | **M-ses** · M-rama (versión sin racha) |
| 13 | `/grupos/nuevo` | `crear_grupos.html` | `group_auth.py` | sí | formulario, error | **M-ses** · M-rama |
| 14 | `/grupos/<id>` | `grupo.html` + `grupo_cabecera`, `grupo_encuestas`, `grupo_modales` | `group_auth.py` | sí | pestaña Planes: tablero (para puntuar, votación, buscando horario, confirmados), sin planes, encuestas abiertas/eligiendo, admin/no admin, modales (invitar, editar, abandonar, hitos) | **M-ses** · M-rama (tablero viejo) |
| 15 | `/grupos/<id>/chat` | `grupo_chat.html` | `group_auth.py` | sí | chat vacío, con mensajes propios/ajenos/agrupados | **M-ses** |
| 16 | `/racha/<id>` | `racha.html` | `group_auth.py` | sí | activa/inactiva, hitos logrados/próximo, calendario semanal, título/marco | **M-ses** |
| 17 | `/grupos/<id>/postular` | `grupo_postular.html` | `grupo_planes.py` | sí | con/sin ideas guardadas, error | **M-ses** |
| 18 | `/grupos/<id>/asistente` | `grupo_asistente.html` + `_chatbot_panel` | `grupo_planes.py` | sí | chat vacío, respondiendo (streaming), borrador de plan | **M-ses** |
| 19 | `/grupos/<id>/encuestas/nueva` | `grupo_encuesta_nueva.html` | `grupo_planes.py` | sí | formulario, error | **M-ses** |
| 20 | `/inbox` | `inbox.html` | `inbox.py` | sí | pestañas Solicitudes / Publicaciones, con y sin invitaciones, solicitudes, avisos leídos/no leídos (**solo medida la pestaña Solicitudes**: abrir Publicaciones marca los avisos como leídos) | **M-ses** · M-rama (versión vieja sin avisos) |
| 21 | `/planes/` | `planes_menu.html` | `planes.py` | sí* | menú de accesos | **M-ses** · M-rama |
| 22 | `/planes/confirmados` | `planes_lista.html` | `planes.py` | sí | con/sin planes | **M-ses** · M-rama |
| 23 | `/planes/grupo` | `planes_lista.html` | `planes.py` | sí | con/sin planes | **M-ses** |
| 24 | `/planes/guardados` | `planes_lista.html` | `planes.py` | sí | con/sin planes, botón "quitar" | **M-ses** |
| 25 | `/planes/archivados` | `planes_lista.html` | `planes.py` | sí | con/sin planes | **M-ses** |
| 26 | `/planes/nueva-idea/asistente` | `planes_asistente.html` + `_chatbot_panel` | `planes.py` | sí* | igual que 18 | **M-ses** |
| 27 | `/planes/nueva-idea` | `planes_nuevo.html` | `planes.py` | sí | formulario, filtros de lugares, buscador con resultados, lista de lugares elegidos, error | **M-ses** · M-rama |
| 28 | `/planes/<plan_id>` | `plan_detalle.html` | `planes.py` | sí | idea, votación, confirmado, archivado, puede puntuar, creador/no creador | **M-ses** |
| 29 | `/perfil` | `perfil.html` + `_social_perfil` | `profile.py` | sí | campos editables, errores por campo, grilla de planes publicados | **M-ses** · M-rama (sin grilla) |
| 30 | `/perfil/cambiar-contrasena` | `cambiar_contrasena.html` | `profile.py` | sí | formulario, error, éxito | **M-ses** |
| 31 | `/usuarios/<id>` | `perfil_publico.html` + `_social_perfil` | `profile.py` | sí | con/sin planes publicados | **M-ses** |
| 32 | `/social/p/<id>` | `social_publicacion.html` | `social.py` | sí | publicación, no encontrada | **M-ses** |
| 33 | `/social/moderacion` | `social_moderacion.html` | `social.py` | sí (+ moderador) | con/sin reportes, foto/texto, eliminado | **M-ses** |

\* `/planes/` y `/planes/nueva-idea/asistente` no chequean sesión en la vista pero dependen del `inject_user` y del menú; hoy un visitante sin sesión es redirigido (confirmado: `/planes/` devuelve 302).

Rutas que **no** devuelven HTML (no se auditan como pantalla): redirecciones (`/productos`, `/planes/historial`, `/planes/nuevo`, `/logout`), unos 45 POST de acciones (votar, cerrar, puntuar, invitar, aceptar, rechazar, publicar, comentar, reportar…) y los JSON de Social (`/social/feed`, `/social/mis-grupos`, `/social/publicables`, comentarios, `/social/fotos/<id>`), del chat (`/grupos/<id>/chat/mensajes`), del chatbot (`/chatbot/*`), de amigos (`/amigos/buscar`) y de lugares (`/planes/buscar-lugares`, `/grupos/<id>/invitables`).

---

## 2. Parciales e incrustados

| Archivo | Tipo | Quién lo incluye | Qué contiene |
|---|---|---|---|
| `_dashboard_sidebar.html` (292 líneas) | parcial | 23 templates con sesión | navegación lateral (8 enlaces con SVG propios, contador del Inbox, botón contraer, reordenado por arrastre) |
| `grupo_cabecera.html` (265) | parcial | `grupo.html`, `grupo_chat.html` | título del grupo con color de rango, marco, descripción, integrantes, acciones, pestañas Planes/Chat |
| `grupo_encuestas.html` (185) | parcial | `grupo.html` | encuestas abiertas y en elección |
| `grupo_modales.html` (670) | parcial | `grupo.html`, `grupo_chat.html` | 4 `<dialog>`: invitar, editar grupo, abandonar, hitos de racha (+ 2 `<script>`) |
| `_chatbot_panel.html` (39) | parcial | `grupo_asistente`, `planes_asistente` | panel del asistente; enlaza `chatbot.css` y `chatbot.js` |
| `_social_perfil.html` (47) | parcial | `perfil`, `perfil_publico` | grilla "Planes publicados"; enlaza `social.css`/`social.js` |
| `_social_plantillas.html` (177) | parcial | `social`, `social_publicacion`, `_social_perfil` | 3 `<dialog>` + 3 `<template>`: tarjeta de publicación, diálogo de la publicación, diálogo "Proponer a mi grupo" y reportar |
| `_social_iconos.html` (17) | macro | `social.html` | 10 íconos SVG de trazo |
| `social.html` | incrustados | — | 1 `<dialog>` ("Compartir un plan") + 2 `<template>` |
| `racha.html` | incrustado | — | 1 `<dialog>` y 377 líneas de `<style>` |
| `amigos.html` | incrustado | — | 1 `<dialog>` ("Invitar a un grupo") |
| `app.js` → `window.preguntar` | diálogo dinámico | toda la app | reemplaza `confirm()` y `alert()` con `<dialog class="modal">` |
| `chatbot.js` | DOM dinámico | asistente | burbujas, "pensamiento", borrador de plan (`className`) |
| `grupo_chat.html` (script) | DOM dinámico | chat | burbujas de mensaje (`classList.add`) |
| `planes_nuevo.html` (script) | DOM dinámico | nueva idea | resultados de búsqueda y lista de lugares elegidos |
| `social.js` | clonado de `<template>` | Social | tarjeta, miniatura, comentario |

Solo en la rama: `_macros.html`, `_garantias.html`, `_topografia.html`.

Diálogos totales en `main`: 10 `<dialog>` escritos en HTML (4 en `grupo_modales`, 3 en `_social_plantillas`, 1 en `social`, 1 en `racha`, 1 en `amigos`), más el que genera `preguntar` por JS, y 5 `<template>` (3 en `_social_plantillas`, 2 en `social`).

---

## 3. Hojas y scripts por página

| Página | CSS | JS |
|---|---|---|
| Todas | `style.css` (6.559 líneas) | `app.js` (1.384) |
| Social, publicación, moderación, perfil, perfil público, inbox | + `social.css` (1.281) | `social.js` (1.032), `social_moderacion.js` (41) en moderación; el Inbox **solo** carga el CSS |
| Asistentes | + `chatbot.css` (336) | `chatbot.js` (450) |
| Racha | + 377 líneas inline | — |
| Chat de grupo, nueva idea, modales de grupo | — | script inline en el propio template |

---

## 4. Matriz de cobertura de la auditoría

Viewports pedidos: 320, 375, 414, 768, 1024, 1280, 1440, 1920. Temas: claro, noche.

| Qué | Cubierto | Cómo |
|---|---|---|
| Páginas públicas de `main` (6 rutas) | **8 viewports × 2 temas = 96 cargas**, capturas a 375 y 1440 | App real en el puerto 5099 sin sesión |
| **Pantallas con sesión de `main` (30 pantallas: las 26 rutas con sesión, con 2 grupos, 2 planes y 3 pestañas de Social)** | **158 cargas**: 375 y 1440 px en claro y noche (30 pantallas), más 320 y 768 px en claro (19 pantallas sin ID); capturas a 375 y 1440 | Cuenta de ejemplo real, base de Supabase, solo lectura (login y GET). Datos reales: 2 grupos, 4 planes, 4 amigos, feed con publicaciones |
| Pantallas heredadas de la **rama Sereno** (14 rutas) | **112 cargas**: 320, 375, 768 y 1440 × claro/noche | Vista previa con datos de ejemplo simulados; **no son las pantallas de `main`** |
| Código: CSS, JS, templates, tokens | Completo | Lectura y conteos |
| Fusión de `main` en la rama | Probada | Worktree descartable, 12 conflictos reales |
| Estilo calculado de elementos que la cuenta no tiene (`.invitation-card`, burbujas, símbolo vacío) | Sí | Elemento inyectado en el DOM del navegador; sin escrituras |

**No cubierto, con el motivo:**

| Qué | Motivo |
|---|---|
| `/inbox?tab=publicaciones` | Abrir esa pestaña **escribe** en la base (`marcar_avisos_leidos`) y la cuenta tiene avisos sin leer; no la visité |
| Estados que la cuenta no tiene: invitaciones pendientes, mensajes propios en el chat, encuestas abiertas/eligiendo, grupo de 1 persona, moderación con reportes (la cuenta no es moderadora), publicación con 2 fotos verticales en detalle | Requieren datos que la cuenta no tiene; crearlos es escribir en la base compartida |
| Estados vacío, error, cargando, textos larguísimos, emojis | Idem; la cuenta solo muestra un estado por pantalla |
| Viewports 414, 1024, 1280 y 1920 con sesión; 320 y 768 en modo noche; 320 y 768 en las pantallas con ID | Se redujo la matriz para terminar la corrida (la base tuvo un corte de red durante la medición) |
| `:hover`, `:active`, lectores de pantalla, `prefers-reduced-motion` | No se probaron |
| Teclado en pantalla **real** (iOS Safari, Android Chrome) | Solo se aproximó achicando la vista a 440 y 340 px (ver `02-HALLAZGOS.md` §C2, IN-09) |
| Interacción y zoom en la **rama Sereno** | Solo se hicieron sobre `main` |
| CLS real y peso de fuentes | No se midió (solo se contó que `img` no declara tamaño) |
| Estado "enviado" de `/contacto` y errores de `/register` | Requieren enviar formularios |

**Cubierto después, solo en `main` con sesión (28 pantallas, ver `02-HALLAZGOS.md` §C2):** orden de tabulación y foco visible (619 paradas), enlace "Ir al contenido", 13 diálogos (abrir, `Esc`, devolver el foco, trampa de foco, tocar afuera, altura en 375×667, 320×640 y 720×450), carrusel con teclado, teclado en pantalla aproximado, zoom 200 %, reflow a 320 px y texto al 200 %.

Para repetir las mediciones con sesión: `redesign-screens/audit/herramientas/medir_sesion.py` (lee las credenciales de las variables de entorno `AQ_USUARIO` y `AQ_CLAVE`).
