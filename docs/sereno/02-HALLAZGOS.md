# 02 — Hallazgos

Auditoría del 2026-10-20. Leé primero **cómo se midió** porque condiciona cuánto confiar en cada fila.

## Cómo se midió y qué significa cada marca

| Marca | Significado |
|---|---|
| **M** (medido) | Medido en Edge (Playwright) con `getBoundingClientRect`/`getComputedStyle`, viewports 320, 375, 414, 768, 1024, 1280, 1440, 1920 en claro y noche (páginas públicas de `main`: 6 rutas × 16 combinaciones) o 320, 375, 768, 1440 en claro y noche (rama Sereno: 14 rutas). Datos crudos en `redesign-screens/audit/`. |
| **C** (calculado) | Salió de los valores del CSS (por ejemplo contraste entre dos tokens), sin verlo en pantalla. |
| **NV** (no verificado) | Deducido de leer código o visto solo en captura, sin medir. Hoy queda para estados que la cuenta de ejemplo no tiene (invitaciones, encuestas abiertas, mensajes propios). |
| **Tipo a / b / c** | (a) defecto del CSS viejo que Sereno ya resuelve solo; (b) sobrevive a la migración si no se corrige; (c) defecto de Sereno mismo. |

**Cobertura (actualizada)**: `main` se midió en sus 6 páginas públicas **y, con una cuenta de ejemplo real (base de Supabase, solo lectura), en 30 pantallas con sesión**: 375 y 1440 px en claro y noche, y 320 y 768 px en claro para las 19 pantallas sin ID. No se midieron: `/inbox?tab=publicaciones` (abrirla marca los avisos como leídos, es una escritura y la cuenta tiene avisos sin leer) ni los estados que esa cuenta no tiene (invitaciones pendientes, mensajes propios en el chat, encuestas abiertas; para varios se verificó el estilo calculado sobre un elemento inyectado, ver C-01 a C-03). La rama Sereno se midió con su **vista previa de datos simulados** (14 pantallas heredadas, no las nuevas). Escala de severidad: S0 rompe el uso, S1 claramente defectuoso, S2 inconsistente, S3 pulido.

**Limitaciones del medidor**: no ve `opacity` de ancestros ni texto sobre imágenes o degradados (puede subinformar elementos atenuados como los hitos "bloqueado" de la racha, y dar falsos positivos sobre fotos e ilustraciones: MS-14).

**Resultado clave de la medición**: en ninguna de las 96 cargas públicas de `main`, las 158 con sesión ni las 112 de la rama hay scroll horizontal (`scrollWidth == clientWidth` en el 100 % de las cargas), y ninguna pantalla devolvió error (los únicos 500 que vi fueron cortes de red de la base, reintentados). **No encontré ningún S0.** Con datos reales, `main` está mejor de lo que temía: el contraste falla casi solo en el contador del Inbox, y los objetivos táctiles chicos son 0 a 8 por pantalla (contra 13 a 37 en la rama Sereno).

---

## A. Defectos del propio Sereno (tipo c) — la migración los trae consigo

Medidos en la rama con datos de ejemplo. Son los más importantes porque **se multiplican por cada pantalla** que se migre.

| ID | Sev | Dónde | Medido vs esperado | Causa raíz | Arreglo propuesto | Esf | Evidencia |
|---|---|---|---|---|---|---|---|
| **S-01** | S1 | Todas las pantallas, claro. `.lead`, `.voice`, `.back-link`, enlaces del footer, `p.auth__alt`, chips inactivos | `--ink-3` sobre `--paper` mide **4,49:1** (mínimo 4,5) y sobre `--paper-deep` (chips inactivos, `.seg`) **4,19:1**. 14 de 14 pantallas fallan; el login falla 15 de 28 textos. | `tokens.css`: `--ink-3: #71706C` | Oscurecer a ≈ `#696964` (≈ 5,2:1 sobre papel, ≈ 4,7:1 sobre `paper-deep`; confirmar con el validador). | S | `sereno-rama/*/medicion__375__claro.json` → `contraste.fallos`; re-medido en R5 (4,49) |
| **S-02** | S1 | Todas. `.meta`, `.chip__count`, `.item__time`, `.plan-tile__meta`, `.cal__weekday`, pie "© 2026" | `--ink-4` mide **2,32–2,56:1** en claro y **3,26–3,59:1** en noche (AA pide 4,5). 57+ nodos en las 14 pantallas; la landing de la rama llega a 38 fallos de 88 textos. | `--ink-4: #A3A29D` (claro) y `#6E6D69` (noche) se usan como color de **texto** (`components.css:39 .meta`) | Reservar `--ink-4` para elementos no textuales (iconos decorativos, separadores). Todo texto meta pasa a `--ink-3`. Si se quiere un 4.º nivel de texto: ≈ `#87877F` en noche. La escala de tinta de texto queda en 3 niveles. | S | `sereno-rama/dashboard/…` R6: 4 nodos, mínimo 2,32 y máximo 2,56 |
| **S-03** | S1 | Todas con sesión (y landing/login) | Objetivos táctiles < 44 px: **13 a 37 por pantalla a 375 px**. Los repetidos: `.dashboard-sidebar-link` 40 px de alto (73 casos), `.icon-btn` tema/menú **40×40** (18+14), `a.logo` 123×29, `.back-link` 40 px, `.btn--sm` 34 px, enlaces del footer 24 px de alto, `.chip` 40, radios del puntaje "0★…5★" 40×43 | `brand.css:202-206 .icon-btn` (40), `brand.css:303-310 .dashboard-sidebar-link` (`height: 40px`), `components.css .btn` (`--h: 42px`, `--sm` 34), `.chip`/`.seg` 40 en celular (`brand.css` §13), `.back-link` (`min-height: 40px`) | Fijar la escala de controles **44 / 48** en celular y dejar 36-40 solo con `@media (pointer: fine)`. Un token `--hit: 44px`. Ver P-02 en `09-PREGUNTAS.md` (el criterio "40/44/48" del prompt contradice el de 44). | M | `…/medicion__375__claro.json` → `tactiles`; R7 (icon-btn 40×40, links 40) |
| **S-04** | S2 | Todas con avatares, badge, calendario | Texto < 12 px: `.badge` de la barra lateral **11 px**; iniciales de `.avatar` de 28-30 px = **10,08–10,8 px**; `.cal__weekday` 11 px | `components.css:119-124`: `font: 600 calc(var(--size) * 0.36)`; `.badge` fija 11 px | `font-size: max(12px, calc(var(--size) * .36))`; badge a 12 px | S | R8, R8b (`10.8px en 30px`, `10.08px en 28px`) |
| **S-05** | S1 (**heredado de `main`**, ver MS-01) | Toda pantalla con sesión, 320–768 px | La barra lateral pasa a tira horizontal: **scrollWidth 845 vs ancho visible 335**; 5 de 8 enlaces (Amigos, Social, Perfil, Planes, Calendario) quedan **fuera de pantalla** y "Grupos" cortado a la mitad. Sin degradado ni flecha que avise que se desliza (`overflow-x: auto`). | `brand.css` sección 07 (layout del dashboard y barra lateral) en `max-width` de celular | Agregar indicio de scroll (máscara degradada + `scroll-snap`) o resolverlo con la fase opcional de navegación (menú + botón "Crear"). | M | `sereno-rama/*/carga__375__*.png`; R9 |
| **S-06** | S2 | `/dashboard` (rama) y landing | `/dashboard` no tiene `<h1>` (medido: 0). La landing salta `h1 → h3` | `home.html` en modo dashboard usa `p.voice` + `.h3` | `<h1>` visible o `visually-hidden` con el saludo | S | R5b; `sereno-rama/inicio/medicion__375__claro.json` → `saltosTitulos` |
| ~~S-07~~ | descartado | `/grupos/<id>` (rama) | `a.idea-menu__item` figuraba "sin nombre", pero en `main` (menú equivalente `a.group-plus-item`) el enlace sí tiene texto y solo `innerText` salía vacío con el menú cerrado. Falso positivo del medidor; no se confirma en la rama | — | — | — | — | — |
| **S-08** | S3 | Todas | Hasta **6 alturas de botón distintas en una pantalla** (`/grupos/g1`: 30, 34, 36, 40, 42, 50) y 5-12 tamaños de fuente (en `/grupos/g1` @1440: 10,08 · 10,8 · 11 · 13 · 15 · 16 · 17 · 18 · 21 · 22 · 29,92 · 52) | Alturas por componente en vez de una escala; `17px` y `29.92px` no son tokens | Escala única de control (S-03) y revisar `17px` y los `calc()` fraccionarios | M | `medicion__1440__claro.json` → `hist` |
| **S-09** | S3 | `.input` y `.btn--lg` | Radio literal **12 px**, que no está en la escala 6 / 9 / 11 / 16 / 20 | `components.css` (`.input`, `.btn--lg`) | Usar `--r-md` (11) o agregar `--r-input` | S | histograma de radios: `12px: 12 usos` |
| **S-10** | S2 | Footer sin sesión (login, registro, landing) | Texto de maqueta visible para el usuario: **"Hecho con Inter y Newsreader"** | `templates/base.html:245` de la rama | Quitar | S | `sereno-rama/login/…__375__claro.json` → `contraste.fallos` (aparece en la lista) |
| **S-11** | S3 | `/dashboard` 1440 | Los 3 accesos ocupan 3 de 4 columnas: contenedor 1104 px, 4 columnas de 267 px, **27 % vacío a la derecha** | `pages.css:341` `repeat(auto-fill, minmax(260px, 1fr))` | `auto-fit` o tope de 3 columnas | S | R11 |
| **S-12** | S1 | Todos los inputs y botones secundarios | Borde de `.input` (`--line-strong`) **1,34:1** contra la superficie (WCAG 1.4.11 pide 3:1); `.btn--secondary` y cards se distinguen solo por `--sh-hair` (1,18:1) | `tokens.css --line-strong` | Borde de controles interactivos a ≥ 3:1 (≈ alfa 0,45) manteniendo `--line` para cards decorativas | S | **C** (calculado; ver `04-MAPA-DE-TOKENS.md` §4) |
| **S-13** | S2 | Landing (rama) | Imagen de la marca sin `width`/`height` (1-2 `img` por página, **medido en 14 de 14** pantallas) | Plantilla del header y footer | Agregar atributos | S | `a11y.imgSinTam` |
| **S-14** | S3 | `/grupos/<id>` 375 | Controles "Sí/No" y "Puedo/No puedo" a la izquierda, con ancho propio, sin ocupar la fila; el enlace "Cerrar votación ahora" es texto muy chico | `.seg` sin `width: 100%` en tarjetas de votación | Segmentado a ancho completo en celular (ver componente 3.6) | S | `sereno-rama/grupos-g1/carga__375__claro.png` (**visual, no medido**) |

---

## B. Defectos de `main` medidos (páginas públicas)

| ID | Sev | Dónde | Medido vs esperado | Causa raíz | Tipo | Esf | Evidencia |
|---|---|---|---|---|---|---|---|
| **M-01** | S2 | Landing, bloque "la base" | Enlaces "VER DISPONIBILIDAD ↗", "VER OPCIONES ↗", "VER PLANES CERCA ↗" de **42 px** de alto (301×42 a 375, 353×42 a 1440); esperado ≥ 44 | `style.css:2147 .pillar-cards a` (`padding-top: 20px`, `--text-xs`, mayúsculas) | a (Sereno rehízo la landing) | S | R1, R1b; `inicio/medicion__375__claro.json` |
| **M-02** | S2 | Landing ≤ 650 px | `.decision-meta` ("01 / AHORA QUÉ") a **9 px** (12 px en escritorio) | `style.css:1975-1979` | a | S | R2 |
| **M-03** | S2 | Landing | **16 tamaños de fuente distintos** a 375 px (17 a 1440) contra 7-9 en el resto: 9, 14, 15, 16, 18, 19, 20, 24, 26, 28, 32, 34, 38, 40, 44, 160 px. 47 valores literales en el CSS (66 declaraciones literales de 175) | `clamp()` literales por sección en `style.css` | a | M | R3 |
| **M-04** | S3 | Todas las públicas | 2 `img.brand-mark` sin `width`/`height` | `base.html` (header y footer) | **b** (sigue en la rama: S-13) | S | R4 |
| **M-05** | S3 | Login y registro | Enlaces en línea 71×18 ("Creala acá") y 83×18 ("Iniciá sesión"); están dentro de una frase, exentos de WCAG 2.5.8 | texto con enlace | b | S | `login/medicion__375__claro.json` |
| **M-06** | S3 | `/explorar` | Botones de **49 y 50 px** mezclados | alturas calculadas por contenido | a | S | `explorar/medicion__375__claro.json` → `alturaBoton` |
| **M-07** | S2 | Landing, `.pillar-icon` | Íconos hechos con caracteres de texto (`◌`, `$`, `↗`): el primero se ve como un círculo punteado, distinto en peso y estilo de los otros dos | `home.html:187` | a | S | `inicio/carga__1440__claro.png` (visual) |
| **M-08** | S2 | Landing "caminar sin apuro" y plan de ejemplo "Salir para hoy" | El texto de la ilustración queda sobre la transición beige → verde. El script reporta 1,09–1,12:1, pero es **falso positivo**: el fondo real es el degradado de la ilustración y el script solo ve el color del contenedor. A ojo, la "S" de "Salir" queda en la zona clara | `.story-card`/`.detail-*` | a (Sereno quitó la ilustración) | M | `plan-caminata-atardecer/carga__375__claro.png`. **No verificado cuantitativamente** |
| **M-09** | S3 | Landing | Las secciones nacen ocultas y aparecen al hacer scroll (`.js .scroll-reveal`): una captura de página completa sale en blanco bajo el hero (pasó en la primera corrida) y `/#como-funciona` apunta a contenido invisible hasta que se scrollea | `style.css:4295-4311` + `app.js` | a (la rama lo quitó) | S | `inicio/carga__375__claro.png` |
| **M-10** | S3 | Todas | 3 familias y 5 pesos cargados de Google Fonts (Figtree 400/600/700, Fraunces 700, JetBrains Mono 500) | `base.html:30-45` | a (Sereno: Inter + Newsreader) | S | `fuentes` en cada JSON |

---

## B2. Defectos de `main` medidos con sesión (cuenta de ejemplo, datos reales)

Rutas medidas: `/dashboard`, `/social` (amigos, descubrir, actividad), `/calendario`, `/amigos`, `/grupos`, `/grupos/nuevo`, 2 grupos, chat, postular, asistente y nueva encuesta del grupo, `/racha/<id>`, `/inbox?tab=solicitudes`, `/planes/*` (7 listas, 2 detalles, nueva idea y su asistente), `/perfil`, cambiar contraseña, un perfil público, una publicación y `/social/moderacion`. La cuenta no es moderadora (la pantalla de moderación se midió tal como la ve esta cuenta). Evidencia: `redesign-screens/audit/sesion-main/<ruta>/`.

| ID | Sev | Dónde | Medido vs esperado | Causa raíz | Tipo | Esf |
|---|---|---|---|---|---|---|
| **MS-01** | **S1** | **Todas las pantallas con sesión en celular.** La barra lateral pasa a una tira horizontal | `scrollWidth` **1004 px** contra 343 visibles a 375 px. A 320 y 375 quedan **fuera de vista 5 de 8 destinos** (Amigos, Social, Perfil, Planes, Calendario) y "Grupos" **cortado a la mitad**; a 414: 4 fuera y "Amigos" cortado; a 768: **2 fuera** (Planes y Calendario). Sin máscara ni flecha que avise que se desliza. Se ve en cada captura (`.../carga__375__claro.png`). | `style.css:1040-1045` (`.dashboard-sidebar-nav` con `overflow-x: auto` en el quiebre móvil) | **b** (Sereno lo hereda: S-05) | M |
| **MS-02** | S2 | Barra lateral y tira, **las 30 pantallas**, claro y noche | Contador del Inbox `span.inbox-notification`: **blanco 12 px sobre `#ef4444` = 3,76:1** (AA pide 4,5 para texto chico); 21×21 px. Es **el único fallo de contraste en la mayoría** de las pantallas (el resto suma `#777`, contadores sobre foto y el número de la racha) | `style.css:928-938` | b (P-08) | S |
| **MS-03** | S2 | `/inbox`, pantalla vacía | Texto `p` en `#777` = **3,98:1 en claro y 4,17:1 en noche** (falla AA); símbolo vacío **lima `#e8ff5a`** fuera de la paleta. Captura: círculo lima brillante sobre crema | `style.css:5295-5308, 5531` | b | S |
| **MS-04** | S2 | `/inbox`, `/social/p/<id>`, `/grupos` | `/inbox` **no tiene `<h1>`** (medido 0): la pantalla arranca directo en las pestañas. `/social/p/<id>` tampoco (0). `/grupos` salta **h1 → h3** | `inbox.html`, `social_publicacion.html`, `grupos.html` | b | S |
| **MS-05** | S2 | Objetivos táctiles < 44 px (375) | Por pantalla 0 a 8. Los repetidos: `button.friend-action` **40×40** (`/amigos`, 8), `button.field-edit-btn` **30×30** (`/perfil`, 3), `button.group-edit-trigger` 40×40, `button.group-plan-link` **145×23** ("Cerrar votación ahora"), flechas del calendario 36×36, `.soc-ver-comentarios` 36 px de alto, `.filtro-lugar` 38 px, enlaces de texto aislados de 22-26 px de alto (título de publicación, "¿Preferís armarla con el asistente?", "Cambiar contraseña →"), `a.group-streak-link` 30×34 | `style.css:5819 .friend-action`, `:3437 .field-edit-btn`, `:6067 .group-plan-link` | b | M |
| **MS-06** | S2 | Texto < 12 px | `.calendario-dia-nombre` **10 px** (7 por pantalla), `.chat-message-author` **11,52 px**, `.chat-message-time` **10,88 px** | `style.css:5170, 6296, 6348` | b | S |
| **MS-07** | S2 | `/planes/nueva-idea` | `input#busqueda-texto` y `select#busqueda-tipo` **sin etiqueta asociada** (ni `<label>` ni `aria-label`) | `planes_nuevo.html:68-71` | b | S |
| **MS-08** | S2 | `/social` y `/grupos/<id>` a 375 px | Las pestañas en píldora **no entran en una fila**: "Actividad" (Social) e "Integrantes" (grupo) saltan a una segunda fila centrada; el resultado se ve desparejo, distinto del Inbox, cuyas dos pestañas sí entran | `style.css:6364 .group-tabs` y `social.css .soc-tabs` (3 implementaciones, C-06) | b | S |
| **MS-09** | S2 | Cabecera de grupo, 375 px | "+ Idea" (verde) e "Invitar" (negro) tienen el mismo peso en la fila, y debajo, a ancho completo, "**Abandonar**" en rojo: la acción destructiva tiene más presencia que "Chat" o "Integrantes". **Visual, no medido** | `grupo_cabecera.html` | b | S |
| **MS-10** | S2 | Votación en el tablero del grupo | Controles "Sí/No" de ~52×44 px alineados a la izquierda, sin ocupar la fila, bajo un botón "Cambiar mi voto" a ancho completo: ritmo inconsistente. El enlace "Cerrar votación ahora" mide 145×23. **Visual + medido** | `grupo.html`, `style.css:6067` | b | S |
| **MS-11** | S3 | Racha, chat, grupo | **Escala tipográfica**: 13 tamaños distintos a 375 px en `/racha` y en el chat, 11 en `/grupos/<id>` y `/grupos`, contra 7-9 en el resto | `<style>` inline de `racha.html`, `style.css` | b | M |
| **MS-12** | S3 | Chat de grupo | Hora del mensaje flotando a la derecha de la burbuja, fuera de su caja; la burbuja ocupa menos de 60 % del ancho disponible. **Visual** | `style.css:6296-6348` | b | S |
| **MS-13** | S3 | `/calendario` | Flechas ← → de 36×36 | `calendario.html` | b | S |
| **MS-14** | — | Contraste no medible | `b` **3,55:1** (contadores de me gusta/comentarios sobre miniaturas, `/social?tab=descubrir`, `/perfil`) y `span.group-streak-number` **1,13:1** (número sobre la llama de la racha): **falsos positivos probables**, el fondo real es una foto o un SVG que el medidor no ve. **No verificado cuantitativamente** | — | — | — |

**Lo que está bien (medido)**: 0 imágenes sin `alt`, 0 controles sin nombre accesible (el único caso, `a.group-plus-item`, tiene texto: ver S-07 descartado), 1 `<h1>` en 28 de 30 pantallas, 0 scroll horizontal, contraste en noche limpio salvo MS-02 y MS-03, y el **feed de Social se ve consistente**: tarjetas con foto, íconos de acción, chips con los datos del plan y comentarios sin desbordes a 375 px.

---

## C. Defectos de `main` detectados en código

Los tres primeros se **verificaron** después con estilos calculados en el navegador (elementos inyectados en el DOM, sin escribir en la base); el resto son hechos de código (conteos, líneas) y no dependen de ver la pantalla.

| ID | Sev | Dónde | Qué dice el código | Causa raíz | Tipo | Esf |
|---|---|---|---|---|---|---|
| **C-01** | S1 **(verificado)** | Inbox, tarjeta de invitación | Fondo `var(--card-bg)` y borde `2px solid var(--border-color)`: ninguno está definido. **Verificado**: `background-color: rgba(0,0,0,0)` y `border: 0 none` en claro y noche (la tarjeta solo conserva su sombra) | `style.css:5348-5351 .invitation-card` | b | S |
| **C-02** | S2 **(verificado)** | Chat de grupo | Burbuja propia **lima `rgb(212,245,90)`** y ajena `rgb(239,239,236)` con texto `rgb(26,26,26)` **idénticos en claro y en noche** (verificado). En la captura nocturna del chat se ve una burbuja clara sobre fondo oscuro | `style.css:6324-6339` | b | S |
| **C-03** | S2 **(verificado en parte)** | Inbox | Verificado: contador `#ef4444`, símbolo vacío `#e8ff5a`, texto `#777`. Sin verificar (la cuenta no tiene invitaciones): botón aceptar `#d9f99d`/`#166534`, rechazar `#fee2e2`/`#b91c1c`, símbolo vacío `#e8ff5a`, contador de la barra lateral `#ef4444`; el bloque `.inbox-empty .empty-symbol` está **duplicado** | `style.css:938, 5295-5308, 5489-5498, 5531-5532, 5852` | b | S |
| **C-04** | S2 | Racha | 377 líneas de CSS dentro del template con 24 hex y 34 clases que solo existen ahí | `templates/racha.html` | b | L |
| **C-05** | S2 | Inbox, publicación suelta | Sin `<h1>`: **confirmado en pantalla** (MS-04) | `inbox.html`, `social_publicacion.html` | b | S |
| **C-06** | S2 | Grupo, Inbox, Social | **3 implementaciones de pestañas** (`group-tab`, `inbox-tabs` que reutiliza `group-tabs`, `soc-tabs`) | CSS | b | M |
| **C-07** | S2 | Toda la app | **17 familias de botón** (40 combinaciones de clase en `<button>`); `header-action-ghost` se usa como botón de formulario; `lime-button` conserva el nombre de una paleta lima que ya no existe | `style.css` | b | L |
| **C-08** | S2 | 21 templates | **26 `<em>` dentro de titulares** (`<h1>…<br /><em>…</em></h1>`) | templates | a | M |
| **C-09** | S2 | Chatbot, Inbox, Perfil, Social | `<link rel="stylesheet">` **dentro del `<body>`** (4 lugares): puede pintar sin estilos y saltar de layout | `_chatbot_panel.html:7`, `_social_perfil.html:7`, `inbox.html:15`, `social.html:18` | b | S |
| **C-10** | S2 | Grupos, racha | **Paleta de 10 rangos + 3 marcos**: 29 hex en `style.css` + 24 en `racha.html`, reglas de noche una por una | `style.css:3885-4440` | b (decisión de diseño, P-04) | L |
| **C-11** | S3 | Amigos, modales | 8 `onclick="…close()"` en línea | `amigos.html`, `grupo_modales.html` | b | S |
| **C-12** | S2 | Social, comentarios, chat | No existen **esqueleto de carga**, toast ni estado de error de red (solo un `hidden` en `data-soc-cargando`) | `social.js:778-822` | b | M |
| **C-13** | S3 | CSS | 8 clases posiblemente muertas (`campo-ayuda`, `check-row`, `crear-plan-guardar`, `friend-search-loading`, `is-disabled`, `social-post-number`, `tone-lilac`, `tone-moss`) | varias | b | S |
| **C-14** | S1 | **Fusión**, `plan_detalle.html` | La rama trae `onsubmit="return confirm(…)"` nativo; `main` ya usa `data-confirmar` + diálogo propio. Si se resuelve mal vuelve el `confirm()` del navegador | conflicto real | b | S |

---

## C2. Interacción, teclado, carrusel y zoom (`main` con sesión, medido)

Pasada del 2026-10-20 con la misma cuenta de ejemplo. **Todo lo que no era GET se bloqueó en el navegador** (0 requests bloqueados: ningún clic intentó escribir). Se midió `main`, **no** la rama Sereno. Datos: `redesign-screens/audit/interaccion-main/` (`foco.json`, `dialogos.json`, `carrusel.json`, `teclado.json`, `zoom.json`, capturas) y `herramientas/interaccion_sesion.py`.

Trampa de medición que conviene recordar: los estilos de foco tienen transición de 160 ms; leer `getComputedStyle` justo después del `Tab` devuelve el estado inicial y marca como "sin indicador" cosas que sí lo tienen. Las dos primeras corridas de foco dieron ese falso positivo; la tercera espera 280 ms. Lo mismo pasó con "el enlace Ir al contenido queda tapado por el header": medido a mano, el enlace queda arriba de todo (`elementFromPoint` es el propio enlace, `z-index: 200`). Descartado.

| ID | Sev | Dónde | Medido vs esperado | Causa raíz | Tipo | Esf |
|---|---|---|---|---|---|---|
| **IN-01** | S2 | Diálogo propio `preguntar` (eliminar amigo, quitar de guardados, eliminar plan) | El foco inicial cae en **"Aceptar"** en 3 de 3 pruebas: con `Enter` se confirma una acción destructiva. Esc, tocar afuera y "Cancelar" sí cancelan y devuelven el foco al botón que lo abrió | `app.js:789`: `autofocus` fijo en el botón Aceptar | b | S |
| **IN-02** | S2 | Diálogos con formulario (editar grupo, invitar, compartir un plan, proponer a un grupo, reportar) | El foco inicial cae en `button.modal-close "Cerrar"` en 10 de 13 diálogos probados (los otros 3 son `preguntar`), no en el primer campo; quien usa teclado o lector tiene que hacer `Tab` para llegar al campo | el botón de cierre es lo primero en el HTML y `showModal()` enfoca el primer elemento | b | S |
| **IN-03** | S2 | "Invitar a un grupo" desde `/amigos` | Al cerrar, el foco **no vuelve al botón que lo abrió**: queda en el último botón de la lista (`focoVuelveAlDisparador: false`) | `app.js:745-760`: un `close` por disparador sobre el mismo `<dialog>`; todos llaman `focus()` y gana el último. Pasa con cualquier diálogo con varios disparadores | b | S |
| **IN-04** | S2 | Diálogos altos | "Editar grupo" y "Compartir un plan" miden **619 px de alto en una vista de 667** (93 %) y su botón final queda en y = 1100 y 840: se llega por scroll interno (existe). A 720×450 (zoom 200 %) hay que desplazar para llegar a "Guardar" o "Publicar". Controles menores a 44 px: Compartir 7, Invitar 4, Integrantes 3, Editar grupo 2. En 320×640 **ningún diálogo es más alto que la pantalla** | `grupo_modales.html`, `_social_plantillas.html` | b | M |
| **IN-05** | — | **Lo que está bien** en diálogos | 13 de 13 abren; **Esc cierra 13/13**; el foco vuelve al disparador en 12/13; tocar afuera cierra 13/13; ningún `Tab` saca el foco del diálogo (solo el ciclo natural hacia el navegador); 13/13 con nombre accesible; los `preguntar` miden 215-243 px y sus botones son ≥ 44 px | `<dialog>` nativo | — | — |
| **IN-06** | S2 | Carrusel de fotos de Social (`[data-soc-fotos]`) | Es un contenedor con `scroll-snap`, **sin botones anterior/siguiente**; los puntos son `<span>` de **7×7 px** sin rol ni etiqueta y, sobre una foto clara, el activo apenas se distingue del resto (visual). Con teclado: el navegador vuelve enfocable el contenedor y **la flecha derecha sí lo mueve** (probado), pero hacen falta unos 60 `Tab` para llegar al primer carrusel. Las fotos sí tienen `alt` ("Foto 2 de …"). Solo había un post de 2 fotos en el feed de la cuenta | `social.js:262-300` | b | M |
| **IN-07** | S3 | Menú "+ Idea" de la cabecera del grupo (`<details>`) | Abre con `Enter`, `Tab` entra a las 3 opciones, pero **`Esc` no lo cierra** (queda abierto con el foco adentro) | `grupo_cabecera.html:58` (`details` sin JS) | b | S |
| **IN-08** | — | **Foco visible, orden y salto** | Se recorrieron **28 pantallas, 619 paradas de `Tab`**: 0 con el foco invisible o fuera de pantalla; "Ir al contenido" es el primer foco y funciona en 28/28 (`Enter` → `#contenido` y el siguiente `Tab` cae en el contenido); campos de texto: borde `--accent` + anillo del 30 % (7,6:1 de contraste del borde, no es un `outline`); el chat muestra el foco en el contenedor `.group-ai-prompt`; el carrusel muestra un trazo verde arriba y abajo. Sin alcanzar por `Tab`: solo ítems de menús cerrados y radios (se mueven con flechas) | `:focus-visible` y focos por componente | — | — |
| **IN-09** | S3 | Teclado en pantalla (**aproximado**: se achica la altura de la vista a 440 y 340 px de 812; no es un teclado real) | Chat, asistente, nueva idea, nuevo grupo y editar nombre del perfil: el campo **queda entero y sin tapar** por la cabecera en los 5 casos. "Compartir un plan": el botón de publicar queda bajo el borde (y = 539 con 440 de vista) y se llega por scroll interno del diálogo; "Nuevo grupo": el botón de enviar queda a y = 374 con 340 de vista | `grupo_modales`, `crear_grupos.html` | b | S |
| **IN-10** | — | **Zoom 200 %** (vista CSS 720×450) | **0 de 28 pantallas con scroll horizontal**; fuente mínima 12 px (10,9 en el chat); la cabecera sticky ocupa 76 px = **17 %** de la altura de la vista; no hay texto útil recortado (lo que reporta el medidor es decoración y un `label` oculto) | — | — | — |
| **IN-11** | S2 | **Reflow a 320 px** (zoom 400 % sobre 1280, vista 320×256) | 27 de 28 pantallas sin scroll horizontal; **`/usuarios/<id>` desborda 22 px** (`.profile-card`, `.auth-intro`, `h1` llegan a 342 px). La cabecera ocupa 64 px = **25 %** de los 256 px de altura | `perfil_publico.html`, estilos del perfil | b | S |
| **IN-12** | **S1** | **Texto al 200 %** en celular (375 px, `html { font-size: 200% }`) | **En 28 de 28 pantallas aparece scroll horizontal de 29 px**: `div.header-controls` y `button.nav-toggle` terminan en x = 404 con una vista de 375, es decir el botón de menú queda **parcialmente fuera de la pantalla**. Además `/usuarios/<id>` +138 px, `/planes/nueva-idea` +91 (selector de filtros a 466), `/perfil/cambiar-contrasena` +72 y `/amigos` +71: títulos largos sin `overflow-wrap` y filas que no se parten. En `/social` los nombres se truncan con elipsis | `style.css` (`.site-header-inner`, `.header-controls`, `h1` con `clamp()`) | b | M |

**Qué NO se probó:** teclado en pantalla real (iOS Safari y Android Chrome tratan `visualViewport` distinto), lectores de pantalla, `prefers-reduced-motion`, foco en Firefox/Safari (el foco de contenedores con scroll cambia entre navegadores), el hilo de comentarios y el diálogo de la publicación abierto desde "Ver los N comentarios" (en esa pantalla el botón expande el hilo en línea, no abre un diálogo), `preguntar` desde "Cerrar votación" (la cuenta no tiene el botón), la rama Sereno (todo esto se midió solo sobre `main`).

---

## D. Descartado o que no es defecto (lo dejo asentado para no repetirlo)

- **Desborde horizontal**: no existe. `scrollWidth == clientWidth` en las 96 cargas de `main` y en las 112 de la rama. Los "elementos fuera de pantalla" que reporta la medición automática (`circle.topo-ring`, `div.story-land`, `div.detail-land`, enlaces de la tira lateral) son recortados o desplazables por diseño (S-05 es un problema de *descubrimiento*, no de desborde).
- **Asimetría** (`form.auth-form izq=756 der=100` a 1440 en login/registro/contacto; tarjetas de la landing): diseño de dos columnas, no un defecto.
- **Contraste en noche de `main` (páginas públicas)**: 0 fallos en las 6 páginas.
- **Contraste en claro de `main` (públicas)**: 0 fallos reales (los únicos 2 son el falso positivo M-08).
- **Alturas de la grilla de accesos** del dashboard de la rama: en una captura parecía que la tarjeta del medio era más alta; re-medida (R11) las tres miden **128 px**. Descartado (la captura se tomó con una animación a medio hacer). Queda solo S-11.
- **`a.skip-link` 1×1**: invisible hasta recibir foco, intencional. Y no queda tapado por la cabecera al enfocarlo (verificado a mano, ver C2).
- **"Sin indicador de foco" y "foco tapado"** de las dos primeras corridas de foco: artefactos de la transición de 160 ms (ver C2).
- **Menú "+ Idea" con enlaces "inalcanzables"**: son ítems de un `<details>` cerrado; abierto se recorren con `Tab`.

---

## E. Re-verificación (autochequeo)

Además de las 11 de abajo, **C-01, C-02, C-03 y MS-01** se re-midieron con una segunda corrida independiente sobre `main` con sesión (estilos calculados y `sidebar_celular.json`) y se confirmaron. Una afirmación de la corrida pública quedó descartada (S-07) y otra (grilla de accesos) también.

### Primera ronda (11 mediciones)

| Hallazgo | Resultado |
|---|---|
| M-01 enlaces 42 px | Se reproduce: 42, 42, 42 a 375 y a 1440 |
| M-02 `.decision-meta` | Se reproduce: 9 px a 375, 12 px a 1440 |
| M-03 tamaños de fuente | Se reproduce: 16 a 375 |
| M-04/S-13 `img` sin tamaño | Se reproduce: 2 `brand-mark` |
| S-01 `--ink-3` 4,49 | Se reproduce: `p.voice` 4,49 |
| S-02 `--ink-4` | Se reproduce: 4 nodos entre 2,32 y 2,56 |
| S-03 40×40 | Se reproduce: 2 `icon-btn` de 40×40 y 8 links de 40 px |
| S-04 texto chico | Se reproduce: badge 11 px; avatar 10,08/10,8 px |
| S-05 tira lateral | Se reproduce: scrollWidth 845 / clientWidth 335, 5 enlaces fuera |
| S-06 sin `<h1>` | Se reproduce: 0 `h1` en `/dashboard` |
| Una afirmación mía provisoria ("tarjeta del medio más alta" en los accesos del dashboard) | **No se reproduce**: se descartó (ver D). No llegó a tener ID |
