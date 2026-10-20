# 04 — Mapa de tokens: CSS viejo (main) → Sereno

Fuentes: `static/style.css` de `main` (bloque `@layer tokens`, líneas 46-204) y `static/css/tokens.css` + `brand.css` de la rama `redesign-sereno` (leídos en un worktree aparte).
Conteos de uso: `var(--x)` sumando `style.css`, `social.css` y `chatbot.css`. Fecha de la auditoría: 2026-10-20.

Convenciones: **calculado** = cuenta hecha desde el valor del token (no se vio en pantalla); **medido** = salió del navegador.

---

## 1. Hallazgo estructural: 27 tokens comparten NOMBRE entre los dos sistemas con valores distintos

Comparten nombre: `--accent --danger --ease --fast --font-display --font-mono --font-sans --ghost --header-h --ink --lift --lift-pressed --line --line-strong --muted --page --radius --radius-pill --radius-sm --scrim --shadow-md --shadow-sm --sidebar-w --sidebar-w-min --surface-1 --surface-2 --surface-3`.

La rama resolvió esto con un "puente" (`brand.css` sección 01) que **redefine los tokens viejos apuntando a los de Sereno**, sin `@layer` para ganarle a las capas de `style.css`. Funciona mientras convivan los dos, pero:

- Tres nombres cambian de **significado** sin cambiar de nombre: `--surface-2` (viejo: verde salvia `#dce7dd`, Sereno: casi blanco para hover/inputs), `--accent` (viejo: verde `#31533f`, Sereno: gris-azul `#5B6A74`), `--text-ui` (viejo: 16 px) vs `--t-ui` (Sereno: 15 px). Quien migre a mano puede equivocarse porque el nombre "suena igual".
- `--line` / `--line-strong` mantienen el nombre pero bajan de alfa 0,16/0,32 a 0,08/0,14 (ver sección 4).
- Cuando se saque `style.css` (Fase 7) el puente se borra y todo `var(--muted)`, `var(--surface-1)`, etc. de `social.css`/`chatbot.css` queda **sin definir** si esos archivos no se migran antes.

## 2. Mapa viejo → Sereno

| Token viejo (valor claro) | Usos | Equivalente Sereno | Estado | Nota |
|---|---:|---|---|---|
| `--page` `#f6f1e6` | 31 | `--paper` | Puente existe | Crema cálido → papel frío (hue 210). Cambio de marca. |
| `--surface-1` `#ebe2cf` | 54 | `--surface` (cards) o `--paper-deep` (bandas) | Puente → `--surface` | Viejo: tarjeta beige sobre fondo crema. Nuevo: tarjeta blanca. Hay que decidir caso por caso cuál de los dos. |
| `--surface-2` `#dce7dd` | 17 | `--paper-deep` | **Colisión de nombre** | El nombre `--surface-2` de Sereno es otra cosa (hover de fila). |
| `--surface-3` `#e3e5e0` | 6 | `--paper-deep` | Puente | |
| `--ink` `#18140f` | 89 | `--ink` `#151515` | Mismo nombre | |
| `--muted` `#55605c` | 103 | `--ink-3` (cuerpo secundario) / `--ink-4` (metadata) | Puente → `--ink-3` | **Baja el contraste**: 5,8:1 → 4,48:1 sobre papel (calculado). Ver sección 4. |
| `--line` rgba .16 | 67 | `--line` rgba .08 | Mismo nombre, otro valor | Bordes de cards casi invisibles. |
| `--line-strong` rgba .32 | 26 | `--line-strong` rgba .14 | Mismo nombre, otro valor | Bordes de inputs: 1,34:1 (calculado). |
| `--accent` `#31533f` | 89 | `--accent` `#5B6A74` | Mismo nombre, otro valor | Verde → gris-azul niebla. |
| `--accent-soft` `#dce7dd` | 9 | — | **Sin equivalente** | Propuesta: `--accent-wash: color-mix(in srgb, var(--accent) 10%, var(--surface))`. Decisión de diseño. |
| `--on-accent` | 17 | `--on-ink` | Sin puente | Los botones primarios pasan a ser **tinta negra**, no acento. Revisar cada uso: texto sobre acento ≠ texto sobre tinta. |
| `--danger` `#8f2f26` | 13 | `--alert` `#C8372D` | Sin puente | Sereno restringe el rojo a "urgencia real". Hoy `--danger` se usa para borrar/abandonar/error. Decisión: ¿se mantiene un rojo "destructivo"? |
| `--danger-soft` | 3 | — | **Sin equivalente** | `color-mix(--alert 10%, --surface)`. |
| `--logout` `#9c4b42` / `--login` `#31533f` | 10 / 5 | — | **Sin equivalente** | Dos colores por acción de sesión. Sereno no los tiene: unificar en `--ink-3`/`--accent`. |
| `--success` / `--success-soft` | 1 / 1 | — | **Sin equivalente (hueco de Sereno)** | Sereno no define verde de éxito. Hoy hay hex sueltos `#d9f99d`/`#166534` en el Inbox. Hay que decidir un token (`--ok`) o resolver con tinta. |
| `--scrim` | 1 | `--scrim` (brand.css) | Igual | |
| `--illus-land`, `--illus-text`, `--illus-text-soft`, `--ghost` | 1 c/u | — | **Sin equivalente** | Ilustración de las "story cards" de la landing. La rama ya la reemplazó (topografía). |
| `--font-display` Fraunces | 10 | `--font-serif` Newsreader / `--brand-headline` | Puente | Cambio de familia. |
| `--font-sans` Figtree | 3 | `--font-sans` Inter | Mismo nombre | |
| `--font-mono` JetBrains Mono | 3 | — | Puente → sans | Se usa en 2-3 etiquetas (`.decision-meta`). |
| `--text-xs` 14 px | 48 | `--t-meta` 13 px | Sin puente | −1 px. |
| `--text-sm` 15 px | 65 | `--t-ui` 15 px | Sin puente | Idéntico. |
| `--text-base` 18 px | 16 | `--t-body` 16 px | Sin puente | −2 px: cambia el ritmo de todo el cuerpo. |
| `--text-md` 20 px | 8 | `--t-lead` (18–21 px fluido) | Sin puente | |
| `--text-ui` 16 px | 7 | `--t-body` 16 px | Sin puente | **Trampa**: `--t-ui` es 15 px. |
| `--max` 1240 | 3 | `--container` 1200 | Sin puente | |
| `--content-gutter` | 8 | `--gutter` | Sin puente | |
| `--header-h` 76 / `--sidebar-w` 248 / `--sidebar-w-min` 76 | 9/1/1 | brand.css redefine 64 / 232 / 64 | Redefinidos | |
| `--proof-h` | 2 | — | Sin equivalente | Banda "MENOS CHAT. MÁS PLANES." de la landing. |
| `--radius` 14 | 24 | `--r-lg` 16 | Puente | |
| `--radius-sm` 10 | 31 | `--r-md` 11 | Puente | |
| `--radius-pill` | 27 | `--r-full` | Puente | |
| `--shadow-sm` / `--shadow-md` | 7 / 3 | `--sh-card` / `--sh-float` | Puente | |
| `--lift` / `--lift-pressed` (sombra sólida 3 px) | 2 / 2 | `--sh-btn` | Puente | Se pierde el gesto "físico" del botón. |
| `--ease`, `--fast`, `--normal`, `--slow` | 78/62/6/8 | `--ease-out`, `--d-fast`, `--d-base`, `--d-slow` | `--ease` y `--fast` con puente; `--normal` y `--slow` **no** | |
| `--group-frame-color`, `--frame-art`, `--frame-shine`, `--hierro`…`--oro` | locales | — | **Sin equivalente** | Paleta de rangos de racha (ver sección 3). |

## 3. Tokens que Sereno no tiene y la app necesita (decisiones de diseño)

1. **Éxito / confirmado** (`--ok`): chips "Confirmado", aviso de guardado, botón "Aceptar".
2. **Rojo destructivo** distinto de `--alert` (urgencia) para "Abandonar grupo", "Eliminar", errores de formulario.
3. **Paleta de rangos de la racha**: 10 títulos (hierro, bronce, plata, oro, esmeralda, hielo, magenta, violeta, amatista, rubí) y 3 marcos (`static/marco-*.svg`). Hoy son 29 hex en `style.css:3885-4440` más 24 hex en el `<style>` de `racha.html`. Sereno es casi monocromo; esta paleta es lo opuesto. Pregunta para `09-PREGUNTAS.md`.
4. **Burbuja de chat** (`--bubble`, `--bubble-own`): hoy salen de hex de respaldo (`#efefec`, `#d4f55a` lima, `#1a1a1a`) porque los tokens `--chat-bubble-*` no existen (ver 5).
5. **Superficies sobre foto** (`rgba(0,0,0,.4/.6)` + `#fff` en `social.css`): chips y contadores sobre imágenes. Necesitan `--on-photo` y `--scrim-photo`.
6. **Tamaño de control**: Sereno define `.btn` 42/50/34 px, `.input` 50 px, `.chip` 32 px; ninguno es 44 px (ver sección 4).

## 4. Defectos de los propios tokens de Sereno (tipo "c")

Cálculo WCAG con los valores de `tokens.css` de la rama (no depende de pantalla):

| Par | Claro | Noche | AA texto 4,5:1 |
|---|---:|---:|---|
| `--ink-3` sobre `--paper` | 4,48 | 6,67 | Claro: **falla por 0,02** |
| `--ink-3` sobre `--paper-deep` (chips inactivos) | 4,18 | 6,29 | Claro: **falla** |
| `--ink-4` sobre `--surface` | 2,56 | 3,25 | **Falla en ambos** (se usa en `.meta`, placeholders, `.chip__count`, `.item__time`) |
| `--ink-4` sobre `--paper` | 2,31 | 3,59 | **Falla en ambos** |
| `--alert` sobre `--paper-deep` | 4,39 | 5,52 | Claro: **falla por 0,11** |
| `--brand-accent` sobre `--paper-deep` | 4,72 | 7,04 | Pasa |
| Borde `--line-strong` contra `--surface` (input) | 1,34 | 1,54 | **WCAG 1.4.11 pide 3:1** para el borde de un control: falla |
| Borde `--line` contra `--surface` (card) | 1,18 | 1,26 | Decorativo: aceptable si el contenido se distingue |

Comparación con el sistema viejo (calculado): `--muted` 5,8:1 sobre `--page` y 7,3:1 en noche. **Migrar a Sereno sin tocar estos tokens baja el contraste de todo el texto secundario.**

Contradicción interna del documento de auditoría: el criterio de aceptación dice "alturas de botón únicas 40/44/48" y también "todo objetivo táctil ≥ 44 px". Un botón de 40 px incumple el segundo (la rama ya fija chips en 40 px en celular, `brand.css` sección 13). Recomendación: tres alturas **44 / 48 / 52** en celular, y 40 solo en escritorio con puntero fino (`@media (pointer: fine)`). Va a `09-PREGUNTAS.md`.

## 5. Tokens usados sin definir en `main` (los de Inbox y chat, **verificados** en el navegador)

| Token | Dónde | Efecto probable |
|---|---|---|
| `--card-bg`, `--border-color` | `style.css:5348-5351` (`.invitation-card`, Inbox) | **Verificado**: fondo `rgba(0,0,0,0)` y borde `0 none` en claro y noche; la tarjeta solo conserva la sombra. |
| `--font-body` | `style.css:2725` (`.crear-plan-contador`) | Cae a la fuente heredada. |
| `--text-lg` | `style.css:6010` | Tiene respaldo `1.25rem`: sin efecto. |
| `--chat-bubble-bg/-text/-own-bg/-own-text` | `style.css:6324-6339` | **Verificado**: siempre usan el respaldo: burbuja propia `rgb(212,245,90)` (lima), ajena `rgb(239,239,236)`, texto `rgb(26,26,26)`, **idénticos en claro y noche**. |

## 6. Valores sueltos fuera de tokens

**`style.css`** (`main`): 78 hex únicos / 91 usos, de los cuales 28 son las definiciones de los tokens y 29 la paleta de rangos. Los 21 restantes:

| Hex | Línea | Contexto |
|---|---|---|
| `#ef4444` | 938 | `.inbox-notification` (contador rojo de la barra lateral) |
| `#e8ff5a`, `#111`, `#777` | 5295-5308, 5531-5532 | `.inbox-empty .empty-symbol` (lima) y texto; **el bloque está duplicado** (5295 y 5531) |
| `#d9f99d`, `#166534` | 5489-5490 | `.invitation-accept` |
| `#fee2e2`, `#b91c1c` | 5497-5498, 5852-5854 | `.invitation-reject`, `.friend-action-danger:hover` |
| `#efefec`, `#1a1a1a`, `#d4f55a` | 6324-6339 | burbujas de chat |
| `#505a66 … #a9ffe0` | 3885-3895 | colores de marcos de racha |

Otros números: 26 `rgba()` sueltos, 47 valores únicos de `font-size` en literal (66 declaraciones de 175), 23 `border-radius` literales de 81, 5 `!important` (4 en reduced-motion y 1 `display:none`).

**`social.css`**: 5 `#fff` y 6 `rgba` negros/blancos, todos sobre fotos; 3 `clamp()` de `font-size`; 0 `!important`. Es el archivo más disciplinado.

**`chatbot.css`**: 0 hex, 0 rgba; usa 57 `var()` y solo 1 `font-size` literal.

**`racha.html`** (bloque `<style>` de 377 líneas dentro del template): 24 hex, 77 `var()`, 2 `@media`. Va a Sereno cuando se resuelva la pregunta de la paleta de rangos.

**`static/*.svg`**: `racha.svg` y los dos `marco-*.svg` llevan colores propios; no son tokens y no se pueden tematizar sin reescribirlos con `currentColor`.

## 7. Tipografías y pesos

| | `main` | Sereno |
|---|---|---|
| Familias | Figtree 400/600/700 + Fraunces 700 + JetBrains Mono 500 (3 pedidos a Google Fonts; **medido**) | Inter 400-700 variable + Newsreader 400-600 (+cursiva) |
| Cuerpo | 18 px | 16 px |
| Tamaños distintos en pantalla (medido, 375 px) | landing 16, resto 7-9 | por definir (se mide en la rama; ver `02-HALLAZGOS.md`) |
