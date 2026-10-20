# 05 — Deuda de código que condiciona la migración (Fase E)

Todo salió de leer y contar sobre `main` (commit `c373acc`) y sobre un worktree de `redesign-sereno`. Lo que no se vio renderizado está marcado **no verificado**.

---

## 1. CSS

### 1.1 Inventario de hojas y orden de carga (`main`)

| Archivo | Líneas | `!important` | Hex | `rgba(` | `@media` | `var(--` usados | Quién lo carga |
|---|---:|---:|---:|---:|---:|---:|---|
| `static/style.css` | 6.559 | 5 | 91 | 26 | 42 | 823 | `base.html` (todas las páginas) |
| `static/social.css` | 1.281 | 0 | 5 | 6 | 4 | 119 | `social.html`, `social_publicacion.html`, `social_moderacion.html`, `inbox.html`, `_social_perfil.html` |
| `static/chatbot.css` | 336 | 0 | 0 | 0 | 2 | 57 | `_chatbot_panel.html` |
| `<style>` inline | 377 | 0 | 24 | 0 | 2 | 77 | `racha.html` |

Defectos de carga:
- `social.css` y `chatbot.css` se enlazan con `<link>` **dentro del `<body>`** (`_chatbot_panel.html:7`, `_social_perfil.html:7`, `inbox.html:15`, `social.html:18`): el navegador puede pintar sin ese CSS y saltar de layout. El salto de layout (CLS) **no se midió**; las capturas finales salen bien porque esperan a que cargue todo.
- `social.css` se carga desde cinco templates distintos en vez de desde `base.html`: al migrar hay que tocar los cinco o centralizar.
- Los números de versión de cache (`v=20261014-admin-grupo-v13`, `v=20261020-social-v6`) son manuales y distintos por archivo: un olvido sirve CSS viejo.

### 1.2 Capas
`style.css` usa `@layer reset, tokens, base, layout, components, pages, utilities` (37 bloques `@layer`; varios bloques `layout`, `components` y `pages` repetidos y entremezclados: `pages` aparece desde la línea 1834 hasta la 5899 con `components` y `utilities` en el medio). `social.css` y `chatbot.css` **no usan capas**: en `main` ganan siempre contra `style.css` por estar fuera de capa, así que hoy un selector de `social.css` pisa a uno de `style.css` aunque tenga menos especificidad. En la rama, `tokens.css`/`components.css`/`brand.css`/`pages.css` tampoco usan capas (a propósito, para ganarle a `style.css`). Al sacar `style.css` hay que decidir si se declara un `@layer` para todo el sistema nuevo (recomendado) o ninguno.

### 1.3 Puntos de quiebre
`@media (max-width: …)` en `main`: 900 px (18 veces), 650 px (14), 700 (2), 560 (2), 480 (2), 500 (1), más `(min-width: 901px) and (min-height: 600px)`, `hover: none` y reduced-motion. `social.css` usa 480 px; `chatbot.css` 650. Hay **seis** puntos de quiebre distintos y ninguno está en un token (las media queries no aceptan `var()`; hay que fijarlos por convención: propuesta 480 / 640 / 900).

### 1.4 Duplicados y reglas pisadas
- `.inbox-empty .empty-symbol` definido dos veces (`style.css:5295` y `:5531`) con los mismos valores.
- `.group-card-streak` / `.group-streak-link` / `.group-title-award--*` / `.group-frame--*` repiten la paleta de rangos en tres bloques (3885-3895, 3955-3964, 4000, 4438).
- Reglas del modo noche escritas selector por selector (`html[data-theme="night"] .group-title-award--hierro {…}`: 10 reglas + variantes) en un sistema que declara "los componentes no necesitan reglas de noche". Solo la paleta de rangos rompe esa promesa.

### 1.5 Clases sin uso aparente (no verificado: pueden generarse por concatenación)
30 clases del CSS no aparecen literales en templates ni JS. De esas, 22 son variantes generadas por concatenación (`group-frame--{{ marco }}`, `group-title-award--{{ color }}`, `soc-portada-{n}`, `chatbot-mensaje-{rol}`), o sea **vivas**. Quedan 8 candidatas a muertas: `campo-ayuda`, `check-row`, `crear-plan-guardar`, `friend-search-loading`, `is-disabled`, `social-post-number`, `tone-lilac`, `tone-moss`. Confirmar con una búsqueda en el navegador antes de borrar.

### 1.6 Cobertura de Sereno sobre el HTML fusionado
Se probó la fusión de `main` en `redesign-sereno` (worktree descartable, ver `07-PLAN-DE-FUSION.md`). Para cada template se contó cuántas clases usadas existen **solo** en el CSS viejo (perderían estilo al borrar `style.css`):

| Template | Clases distintas | Solo en `style.css` | Solo en `social.css`/`chatbot.css` | Sin definición en ninguna hoja |
|---|---:|---:|---:|---:|
| `grupo_encuestas.html` | 21 | **21** | 0 | 0 |
| `grupo_cabecera.html` | 33 | **21** | 0 | 11 |
| `grupo.html` (lado main) | 71 | 22 | 0 | 7 |
| `inbox.html` | 56 | 19 | 7 | 7 |
| `grupo_modales.html` | 36 | 15 | 0 | 10 |
| `grupo_chat.html` | 12 | 9 | 0 | 1 |
| `grupo_encuesta_nueva.html` | 11 | 8 | 0 | 0 |
| `social.html` | 71 | 12 | 17 | 13 |
| `planes_nuevo.html` | 46 | 10 | 0 | 1 |
| `racha.html` | 46 | 4 | 0 | **34** (las define su `<style>` inline) |
| `_social_plantillas.html` | 50 | 4 | 38 | 0 |
| `social_moderacion.html` | 21 | 5 | 13 | 0 |

Lectura: las pantallas heredadas (landing, login, planes, perfil, amigos, calendario) ya tienen casi todo en Sereno; **las funciones nuevas (grupo, encuestas, chat, racha, social, inbox) no tienen casi nada**.

---

## 2. JavaScript acoplado a clases

| Archivo | Líneas | Clases usadas como selector (`querySelector`/`closest`/`matches`) | Clases que alterna (`classList`) | `data-*`/`dataset` | Estilos en línea | `innerHTML` |
|---|---:|---|---|---:|---:|---:|
| `app.js` | 1.384 | `dashboard-sidebar-link`, `field-edit`, `field-edit-btn`, `field-editable`, `field-view` | `is-collapsed`, `is-dragging`, `is-empty`, `is-leaving`, `is-reordering`, `is-visible`, `scroll-reveal` | 30 | 2 (`transform` de la barra de progreso; `cssText` de un campo oculto, `app.js:704`) | 3 |
| `social.js` | 1.032 | `modal`, `soc-comentario`, `soc-miniatura`, `soc-tarjeta` | `is-activo`, `is-pop`, `soc-grilla`, `soc-lista` | 134 | 0 | 0 |
| `chatbot.js` | 450 | `chatbot-borrador`, `chatbot-mensaje` | `chatbot-transmitiendo` | 1 | 0 | 0 |
| `social_moderacion.js` | 41 | `mod-item` | — | 8 | 0 | 0 |

Lectura:
- **`social.js` está bien hecho**: casi todo por `data-soc-*` (134 usos). Migrar su CSS no rompe la lógica.
- **`chatbot.js` construye el DOM con `className`** (unas 15 clases: `chatbot-borrador*`, `chatbot-accion`, `chatbot-pensamiento*`, `chatbot-mensaje-{rol}`): si se renombran en el CSS hay que renombrar en el JS. Candidato a `data-*` o a mantener los nombres.
- **Scripts inline en templates** (10 templates con `<script>`): `grupo_chat.html:222-270` arma las burbujas con `classList.add("chat-message", "is-own", "is-grouped", "chat-bubble", "chat-message-author", "chat-message-line", "chat-message-time")`; `planes_nuevo.html:204-325` arma la lista de lugares con 8 clases `crear-plan-*`. En la fusión, la rama ya cambió una de ellas (`input planner-stop__time`) y `main` otra (`crear-plan-elegido-campo`): es uno de los conflictos reales (hunk 2 de `planes_nuevo.html`).
- **Clases de estado `is-*`**: `is-visible`, `is-leaving`, `is-collapsed`, `is-empty`, `is-dragging`, `is-reordering`, `is-activo`, `is-pop`, `is-own`, `is-grouped`, `is-elegido`, `is-active`. Son contrato JS↔CSS. Convención propuesta para Sereno: pasarlas a atributos (`data-estado="…"`, `aria-*`) a medida que se toque cada componente, no en bloque.
- **Handlers en línea**: 8 `onclick="document.getElementById('modal-…').close()"` (`amigos.html`, `grupo_modales.html`) y, **del lado de la rama**, `onsubmit="return confirm(…)"` en `plan_detalle.html` (la rama no trae el `data-confirmar` ni el diálogo propio `preguntar` de `app.js:773`). Al fusionar hay que quedarse con `data-confirmar`.
- **`confirm()`/`alert()` nativos**: ninguno en `main` (reemplazados por `window.preguntar`, `app.js:773`). En la rama sobreviven en `plan_detalle.html` (hunk de conflicto).

---

## 3. Templates

- **`<em>` dentro de titulares**: 26 titulares en 21 templates (`amigos`, `calendario`, `cambiar_contrasena`, `contacto`, `crear_grupos`, `explorar`, `grupo_asistente`, `grupo_encuesta_nueva`, `grupo_postular`, `grupos` ×3, `home` ×4, `login`, `perfil`, `plan`, `planes_asistente`, `planes_menu`, `planes_nuevo`, `racha`, `register`). Todos con el patrón `<h1>… <br /><em>…</em></h1>`. En Sereno son la tinta de énfasis; la regla del proyecto dice cero `<em>`.
- **Jerarquía de títulos**: `inbox.html` arranca en `<h2>` sin `<h1>` (líneas 56, 154, 187, 326); `social_publicacion.html` no tiene `<h1>` (solo `<h2>` en el estado "no encontramos esta publicación"); `grupos.html` y `home.html` tienen 2 `<h1>` pero son ramas condicionales (logueado / no logueado), no un defecto. `social_moderacion.html` y `perfil_publico.html`: confirmar (**no verificado**).
- **Estilos en línea**: 1 (`racha.html:435`, `style="width: …%"` de la barra de progreso: legítimo, es un dato). Cero `style=` en el resto de `main`. La rama agrega `style="--h:…; --size:28px"` en un macro de avatar (legítimo: variable CSS).
- **`<style>` en template**: solo `racha.html` (377 líneas).
- **SVG repetidos**: `_dashboard_sidebar.html` 8, `planes_menu.html` 6, `grupo_modales.html` 6, `grupo_cabecera.html` 6, `amigos.html` 4, `home.html` 2. Íconos de trazo copiados a mano sin parcial común (Social sí tiene `_social_iconos.html`, 10 íconos). Propuesta: un solo `_iconos.html` con el macro `ico(nombre)` de Social, generalizado.
- **Accesibilidad a nivel plantilla**: 18 templates con `aria-label` en 0 usos (`cambiar_contrasena`, `contacto`, `crear_grupos`, `grupo`, `grupo_asistente`, `grupo_encuesta_nueva`, `grupo_encuestas`, `grupo_postular`, `home`, `login`, `perfil_publico`, `plan`, `plan_detalle`, `planes_asistente`, `planes_lista`, `planes_menu`, `register`, `social_moderacion`). Puede estar bien si usan texto visible; hay que revisar los botones de solo ícono en pantalla (**no verificado**).
- **Imágenes**: el isotipo de la marca (`<img class="brand-mark">`, header y footer) no declara `width`/`height`: 2 `img` sin tamaño en **todas** las páginas (medido). Salto de layout menor.
- **Inputs**: de 16 combinaciones de `<input>/<select>/<textarea>`, 14 no llevan clase: se estilan por selector de elemento. Es una ventaja para migrar (un solo lugar), siempre que Sereno defina `input, select, textarea` globalmente y no solo `.input`.
- **Botones**: 40 combinaciones distintas de `class` en `<button>` (ver `03-COMPONENTES.md`).

---

## 4. Repositorio y entorno

- **`__pycache__/*.pyc` versionados**: 71 archivos en `main`, 43 en la rama, aunque `.gitignore` los excluye (se agregaron antes del ignore). Cada vez que se corre la app, `git status` muestra `.pyc` modificados (hoy: `__pycache__/database.cpython-314.pyc`, `models/__pycache__/user.cpython-314.pyc`, `routes/__pycache__/group_auth.cpython-314.pyc`) y en una fusión pueden dar conflictos de binarios. Sacarlos del índice con `git rm -r --cached` es un cambio aparte, no de este rediseño.
- **Ruta larga**: la carpeta del proyecto está bajo OneDrive con espacios y `#`; un `git worktree add` dentro del árbol falló con "Filename too long" (se resolvió usando `C:\tmp`). Cualquier worktree de la migración tiene que vivir en una ruta corta.
- **Worktree ajeno**: existe `…/.kilo/worktrees/elastic-ocicat` (HEAD desprendido en `cd001ec`), de otra herramienta. No se tocó.
- **Archivos en la raíz que no son del producto**: `chatbot.patch`, `lugares_osm_nuevos.csv`, `lugares_osm_nuevos.html`. No afectan al rediseño.
- **Rama sin respaldo**: `git ls-remote --heads origin redesign-sereno` devuelve vacío (verificado). 12 commits propios, 59 commits de atraso respecto de `main` (`git rev-list --left-right --count redesign-sereno...main` → `12 59`).
- **Medición de tiempos en producción**: `app.py:75-84` imprime el tiempo de cada request ("sacar cuando no haga falta"); no es del rediseño, pero ensucia la consola mientras se mide.
