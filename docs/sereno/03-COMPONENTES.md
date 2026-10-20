# 03 — Catálogo de componentes: variantes actuales, mapeo a Sereno y especificación de lo que falta

Base: `main` (`c373acc`) y `redesign-sereno` (`d88235b`). Conteos de variantes salen de las clases en `templates/*.html` y de las reglas de `style.css`/`social.css`/`chatbot.css`. Nada de esto se vio renderizado salvo lo indicado como **medido** (páginas públicas de `main`, ver `02-HALLAZGOS.md`).

---

## 1. Lo que Sereno ya define (`tokens.css`, `components.css`, `brand.css`)

`.container .section .stack-y .dot-grid` · `.display .h2 .h3 .lead .body .meta .voice` · `.btn` (`--primary --secondary --ghost --lg --sm --block`) · `.input` · `.field-row` · `.kbd` · `.badge` · `.chips/.chip` · `.seg` · `.avatar` · `.card (--float --pad)` · `.item` · `.pile` · `.window` · `.trust` · `.steps` · `.nav` · `.faq`.
`brand.css` (rama) agrega lo propio de Ahora Qué: header, botón de ícono, footer, layout del dashboard y barra lateral, modales, avisos, card de plan, pantalla de una sola acción, mensajes de formulario, tamaños táctiles, página interna, etiquetas, listas de planes y estado vacío, recorrido de lugares, controles de formulario (select, chips con casilla, puntaje), detalle de plan, lista de accesos, integrantes y menú desplegable, perfil y estrellas, voz, textura de cabecera.

Tamaños reales de Sereno (leídos del CSS): `.btn` 42 px (`--lg` 50, `--sm` 34), `.input` 50 px, `.chip` 32 px (40 en celular), `.seg button` 30 px (40 en celular), `.badge` 20 px, `.kbd` 22 px, `.avatar` 44 px. **Ningún control base llega a 44 px en escritorio**, y 34 y 42 no entran en la regla "40/44/48" del documento de auditoría. Ver `04-MAPA-DE-TOKENS.md` §4.

---

## 2. Catálogo por componente

### 2.1 Botón
**Hoy en `main`: 17 familias de clase** aplicadas a `<button>`/`<a>` (40 combinaciones distintas de `class` en `<button>`):

| Clase actual | Dónde | Usos | Mapeo a Sereno |
|---|---|---:|---|
| `lime-button` (primario; el nombre es herencia de una paleta lima que ya no existe) | 7 `<a>` + 19 `<button>` | 26 | `.btn .btn--primary` |
| `plan-accion-secundaria` | grupo, plan_detalle, social, perfil | 11 | `.btn .btn--secondary` |
| `header-action header-action-ghost` (usado como botón secundario de formularios, no solo del header) | amigos, modales, encuestas, social | 8+ | `.btn .btn--ghost` o `--secondary`; **error de nombre**: es un botón de formulario con nombre de header |
| `dark-button` | cabecera de grupo, encuestas | 5 | `.btn .btn--primary` |
| `text-button` | 1 | 1 | `.btn .btn--ghost` |
| `plan-accion-peligro` | plan_detalle | 1 | **falta**: `.btn--danger` |
| `logout-button` | cabecera de grupo ("Salir del grupo") | 1 | **falta**: `.btn--danger` |
| `field-edit-btn` / `field-save-btn` | perfil | 6 | `.btn .btn--sm` |
| `friend-action` / `friend-action-danger` | amigos, modales | 4 | **falta**: botón de ícono redondo 40 px (Sereno tiene botón de ícono en `brand.css` sección 05, de 36-40 px) |
| `invitation-action invitation-accept/-reject` | inbox | 4 | `.btn --primary` / `--secondary`; hoy llevan hex sueltos (`#d9f99d`, `#fee2e2`) |
| `groups-nav-button` | grupos | 2 | botón de ícono 50 px circular |
| `filter-chip` | explorar | 2 | `.chip` |
| `chatbot-nueva`, `chatbot-accion(-principal)`, `lime-button chatbot-enviar` | chatbot | 4 | `.btn --sm`, `.btn --primary`; hoy 46 px de alto |
| `soc-icono` (44 px), `soc-icono-chico`, `soc-accion`, `soc-accion-guardar`, `soc-ver-comentarios`, `soc-previa-quitar`, `soc-miniatura` | social | 14 | **falta**: botón de acción del feed (ícono + contador) |
| `modal-close` | 9 modales | 9 | botón de ícono de modal (Sereno `brand.css` sección 08) |
| `group-tab`, `group-edit-trigger`, `group-plan-link`, `group-ai-prompt-send` | grupo | 5 | ver pestañas (§2.7); resto `.btn` |
| `theme-toggle`, `nav-toggle`, `dashboard-sidebar-toggle` | shell | 3 | botón de ícono (ya resuelto en la rama) |

Alturas medidas en `main` (páginas públicas): botones principales 48-50 px (explorar tiene 49 y 50 mezclados: 1 px de diferencia), 42 px en los enlaces "VER …" de la landing, 18 px en enlaces en línea de login/registro (exentos si están dentro de una frase; WCAG 2.5.8).
Alturas encontradas en CSS: 34, 36, 40, 44, 46, 48, 50, 52 px. **Alturas propuestas**: 44 (normal), 48 (grande), 36 solo con `@media (pointer: fine)` para escritorio.

Brechas de Sereno: `--danger`, ícono solo (circular), botón de acción de feed, estado `:disabled` (la rama usa `opacity`; definir), estado de carga.

### 2.2 Campos de formulario
`main`: 16 combinaciones de `<input>/<select>/<textarea>`, **14 sin clase** (se estilan por selector de elemento) → buena base. Tipos en uso: text (14), radio (12), textarea (8), password (5), checkbox (6), search (4), time (4), date (3), email (2), select (3), file (1, oculto con `visually-hidden`).
Mapeo: `.input` de Sereno + `select`, `textarea` (la rama ya los trae en `brand.css` §18: select, chips con casilla, puntaje).
Brechas de Sereno:
- `.input` tiene borde de 1,34:1 (falla 1.4.11).
- No hay `.textarea`, `.field` (etiqueta + ayuda + error) ni `.checkbox`/`.radio` propios.
- `<input type="date">` y `type="time"`: el control nativo es inconsistente entre navegadores; en celular abre el selector del sistema. Decidir si se estiliza o se deja nativo.
- El diálogo "Compartir un plan" de Social tiene un selector de archivos oculto + vista previa con miniaturas: componente propio (§3.1).

### 2.3 Chips, etiquetas, insignias
`main`: `filter-chip` (46 px), `encuesta-chips`, `section-tag`, `group-tab-count`, `soc-datos` / `soc-mini-datos` (chips con los datos del plan: tiempo, precio, personas), contador rojo `.inbox-notification` (`#ef4444`), estados de plan ("Confirmado", "En votación", "Idea", "Archivado").
Sereno: `.chip`, `.badge`, `.chips` (segmentado). Brechas: **chip de dato** (ícono 20 px + texto, sin interacción), **chip de estado** (con `--ok`/`--alert`/neutro), contador con `--alert`. La regla "rojo solo para urgencia real" decide si el contador del Inbox va en rojo (pregunta en `09`).

### 2.4 Tarjeta
`main`: 20 clases `*-card` (`group-card`, `plan-card`, `friend-card`, `invitation-card`, `profile-card`, `story-card`, `index-card`, `postular-idea-card`, `pillar-cards` …) más `soc-tarjeta`. Cada una define su propio padding/radio/sombra. Radios medidos en las páginas públicas: 10 px y 14 px (más 999 px y 50%).
Sereno: `.card` (radio 16 px, `--sh-card`) y `.item`. La rama ya tiene `.plan-tile` y `.card--pad`. Brechas: tarjeta de grupo con marco de insignia (§3.4), tarjeta de votación (§3.6), tarjeta de publicación (§3.1).

### 2.5 Modal / diálogo
`main`: `<dialog class="modal">` con 15 clases `modal-*` (4 en `grupo_modales.html` — invitar, editar grupo, abandonar, hitos de racha —, 1 en `amigos.html`, 3 en `_social_plantillas.html`, 1 en `social.html`, 1 en `racha.html`) más el diálogo dinámico `window.preguntar` (`app.js:773`) que reemplaza `confirm()`/`alert()`.
Sereno/rama: modales en `brand.css` §08 (ventana `--r-xl`, `--scrim`). Falta verificar: foco inicial, devolución del foco, `Esc`, diálogos más altos que la pantalla en 320×640, y que `preguntar` tome el estilo nuevo. 8 `onclick="…close()"` en línea para cerrar.

### 2.6 Avisos (flash, toast, "cargando", vacío)
`main`: `.flash-stack/.flash-message` (en `base.html`, solo con sesión), `aviso-*` (7 clases), `*-empty` (9 variantes: `empty-symbol`, `friend-search-empty`, `group-board-empty`, `groups-empty`, `inbox-empty`, `plan-index-empty(-inline)`, `social-feed-empty`, `is-empty`), `friend-search-loading` (sin uso aparente). Social muestra un indicador `data-soc-cargando` (se oculta con `hidden`, `social.js:778-822`); **no existe esqueleto de carga ni toast** en ninguna hoja (verificado con `grep`).
Sereno: avisos y estado vacío en `brand.css` §09 y §16/§23. Brechas: **esqueleto de carga** (feed, comentarios, chat), **toast** de confirmación y **error de red** del feed: hoy no existen.

### 2.7 Pestañas
**Tres implementaciones distintas**: `group-tab(s)` (grupo: Planes/Chat/Integrantes), `inbox-tabs` (Solicitudes/Publicaciones, que además reutiliza `group-tabs`) y `soc-tabs` (Amigos/Descubrir/Actividad), más `nav` interna de la barra lateral. Sereno ofrece `.chips` y `.seg`. Propuesta: un solo componente `.tabs` (rol `tablist`, `aria-selected`, flechas del teclado), con contador opcional (`.chip__count`).

### 2.8 Avatar
`main`: `avatar`, `avatar-a…d` (4 colores), `friend-avatar`, `modal-member-avatar` (34 px), `soc-avatar` (36 px), avatares en burbujas de chat. Tamaños en CSS: 28, 34, 36, 40, 44, 48, 72, 96 px.
Sereno: `.avatar` con `--size` y `--h` (matiz) → **cubre todos**; la rama ya usa `--size: 28px`. Falta la escala oficial (propuesta 28 / 36 / 44 / 72).

### 2.9 Menú desplegable y navegación
`main`: sidebar contraíble con reordenado por arrastre (`is-dragging`, `is-reordering`; `app.js`), menú "+" del grupo, `<details>` en perfil. Header con `nav-toggle` en celular. Medido: header sticky 64 px en 375 y 76 px en 1440; `scroll-progress` fijo de 3 px.
Sereno/rama: header `app-header`, sidebar de 232/64 px y menú desplegable (`brand.css` §21). Brecha: en la rama se borró la barra de progreso de scroll.

---

## 3. Componentes que faltan en Sereno (especificación lista para implementar)

Unidades: tokens de `tokens.css`. Todos deben tener modo noche, `:focus-visible`, `prefers-reduced-motion` y objetivo táctil ≥ 44 px donde haya interacción.

### 3.1 Feed de publicaciones (Social)
Anatomía: `article.post` → `header` (avatar 36 + nombre + "hace N" en `--t-meta`/`--ink-4`) → `figure` (foto o portada) → barra de acciones → "Les gusta a…" → título/chips → vista previa de comentarios.
- Contenedor `--r-lg`, `--sh-card`, ancho máximo 520 px centrado (feed) / grilla de miniaturas 3 columnas con `gap: var(--s-1)` en Descubrir.
- Foto: relación fija **4:5** (hoy `social.css` usa tres: `1 / 1` en `.soc-fotos` y `.soc-miniatura`, `16 / 10` en `.soc-portada`, `4 / 5` solo cuando `.soc-fotos[data-aspecto="vertical"]`; unificar o documentar la regla), `object-fit: cover`, reserva de espacio para evitar salto de layout. Portada sin foto: 3 variantes de color (`soc-portada-0/1/2`) hoy con colores propios → tokens `--cover-1..3` derivados de `--paper-deep`/`--accent`.
- Acciones: 4 botones de ícono de 44×44 (me gusta, comentarios, proponer a grupo, guardar), trazo 1,75 px, `aria-pressed` en me gusta y guardar, contador con `tabular-nums`.
- Me gusta: animación "pop" ya existe (`is-pop`, 96 px); en reduced-motion, solo cambio de color.
- Estados: cargando (esqueleto 4:5 + 3 líneas), vacío ("Todavía no hay planes de tus amigos" + botón), error.
- Noche: el pie y el texto sobre foto usan `--on-photo` (blanco) y `--scrim-photo` (negro 40-60 %); hoy `rgba` sueltos en `social.css:281,664,764,941,1159`.

### 3.2 Carrusel de hasta 2 fotos
Scroll horizontal con `scroll-snap-type: x mandatory`, puntos indicadores de 6 px (`is-activo`) separados por `--s-1`; accesible con flechas (botones ocultos en táctil, visibles con `:hover`/`:focus-visible` en puntero fino). Ya existe la lógica en `social.js`; solo falta el diseño con tokens.

### 3.3 Diálogo "Compartir un plan" (formulario largo en modal)
Estructura: selector de plan (lista elegible con radio, `--r-md`), texto (`textarea` 4 filas, contador `--t-meta`), 0-2 fotos con vista previa 72 px y botón de quitar de 44 px, formato (segmentado `.seg`), visibilidad (`.seg`), acciones al pie fijas (`position: sticky; bottom: 0`) para que el botón sea alcanzable cuando el diálogo es más alto que la pantalla (**verificar en 320×640**).

### 3.4 Insignias y marcos de racha
Anatomía actual: 10 títulos coloreados (`group-title-award--*`), 3 marcos de imagen (`static/marco-*.svg`), llama (`racha.svg`), barra de progreso al próximo hito, calendario semanal de 7 días (`dia.hecho`), lista de hitos (`hito.logrado/proximo`).
Falta en Sereno: **paleta de rangos** (decisión de diseño, ver `09-PREGUNTAS.md` P-04), componente `.badge--rank` y `.frame` (borde con degradado) tematizables. Mientras no se decida, se mantienen los hex en un único bloque `/* RANGOS */` en `brand.css` (excepción documentada a la regla "cero hex").

### 3.5 Burbujas de chat y panel del asistente
- **Chat de grupo** (`grupo_chat.html`): burbuja ajena `--surface` con radio `--r-lg --r-lg --r-lg --r-xs`, propia `--ink`/`--on-ink` (negra, coherente con el botón primario) con radio `--r-lg --r-lg --r-xs --r-lg`; agrupadas: esquinas parejas; autor en `--t-meta`; hora `--ink-4` (**no usar `--ink-4` para texto: falla AA**, usar `--ink-3`). Ancho máximo 78 % del contenedor; `overflow-wrap: anywhere`. Hoy: `#efefec`/`#d4f55a`/`#1a1a1a`.
- **Panel del asistente** (`chatbot.css`): contenedor `.card`, mensajes con el mismo componente de burbuja, "pensamiento" en cursiva `--ink-3`, **borrador de plan** como tarjeta con título, descripción, lista de lugares y dos acciones (`.btn--primary`, `.btn--secondary`). Estado `chatbot-transmitiendo` con cursor parpadeante (respetar reduced-motion).

### 3.6 Tarjeta de votación (plan y horario)
Anatomía: título, meta (fecha, hora, lugares, precio), contador "N de M votaron", dos botones de voto de ancho igual ("Me gusta" / "Puedo": 2 ejes), barra de avance (4 px, `--accent`), acciones del creador ("Cerrar votación"). Variante horario: lista de opciones con radio y conteo.
Estados: sin votar / votó / cerrada / empate. Hoy `is-elegido` marca el voto propio.

### 3.7 Tablero por estado (grupo)
Cinco secciones (`para puntuar`, `votación`, `buscando horario`, `confirmados`, vacío) con encabezado `.h3`, contador y lista de tarjetas. En celular: una columna; en 900 px+: lista, no grilla. Estado vacío con acción primaria.

### 3.8 Chips de datos del plan
Fila con `gap: var(--s-2)`, `flex-wrap`, chip de 28 px de alto no interactivo (distinto del `.chip` de 32/40 px que sí lo es), ícono de 16 px y texto `--t-meta`. Tipos: duración, precio (`$ 300–600`), personas, lugar. Texto truncado con elipsis y `title`.

### 3.9 Encuestas ("armar un plan entre todos")
Estados: abierta, eligiendo, cerrada, cancelada; opciones de respuesta por nivel (`mi_nivel`, `mi_menores`); acción "elegir" para el creador. Componente tipo lista de preguntas con radios grandes (44 px) y resumen con barras. Hoy `grupo_encuestas.html` usa **21 clases, todas solo en `style.css`**.

### 3.10 Avisos del Inbox
Pestañas Solicitudes / Publicaciones; ítem con avatar, texto, hora, punto de "no leída" (6 px, `--accent`, no rojo) y acción. Reutiliza `.item` de Sereno (`.item__time--alert` solo para urgencia real).

### 3.11 Otros
Diálogo de reporte (radios de motivos + textarea), hilo de comentarios (lista + campo fijo abajo, con teclado en pantalla), grilla de "Planes publicados" del perfil (3 columnas, relación 1:1 con `gap: var(--s-1)`), cabecera de pantalla con textura de puntos (ya en la rama §24), pantalla de moderación (tabla de reportes con acciones; **no verificado**).
