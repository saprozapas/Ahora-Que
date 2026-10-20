# 00 — Resumen de la auditoría del rediseño "Sereno"

Fecha: 2026-10-20 · `main` en `c373acc` · rama `redesign-sereno` en `d88235b` · producto sin modificar (solo se crearon archivos en `docs/sereno/` y `redesign-screens/audit/`; nada commiteado).

## Estado general

- **No hay ningún defecto S0**: en las 96 cargas públicas de `main`, las 158 con sesión (cuenta de ejemplo, base real) y las 112 de la rama no existe scroll horizontal ni errores de página. **`main` está mejor de lo que temía**: el contraste falla casi solo en el contador del Inbox (3,76:1) y hay 0 a 8 objetivos táctiles chicos por pantalla.
- **El riesgo no está en lo que ya se rediseñó sino en lo que falta y en Sereno mismo.** La rama cubre bien las pantallas heredadas; las funciones agregadas después (grupo con tablero, encuestas, chat, racha, social, inbox con avisos) **no tienen casi nada de Sereno** (`grupo_encuestas.html`: 21 de 21 clases solo existen en el CSS viejo).
- **Cobertura**: se midieron las 6 páginas públicas y **30 pantallas con sesión de `main`** (375 y 1440 px en claro y noche; 320 y 768 en claro para las 19 sin ID). También se midió interacción (foco, `Esc`, diálogos, carrusel, teclado en pantalla aproximado) y zoom (200 %, reflow a 320 px, texto al 200 %), solo en `main`. Quedan sin medir: la pestaña Publicaciones del Inbox (abrirla escribe en la base), estados que la cuenta no tiene (invitaciones, encuestas abiertas, mensajes propios), teclado en pantalla real y lectores de pantalla.

## Los 15 problemas más graves

| # | Problema | Sev | Evidencia |
|--:|---|---|---|
| 1 | La rama `redesign-sereno` **existe solo en la compu de Santi** (12 commits propios, 59 de atraso) | — | `git ls-remote` vacío; `07` |
| 2 | **Contraste de Sereno bajo AA**: `--ink-3` 4,49:1 (lead, voz, enlaces) y `--ink-4` 2,3-2,6:1 en claro / 3,3-3,6 en noche (meta, contadores, horas). Falla en **14 de 14** pantallas medidas | S1 | S-01, S-02 |
| 3 | **Objetivos táctiles < 44 px**: 13 a 37 por pantalla en celular (menú, tema, enlaces de la barra lateral 40 px, `.btn--sm` 34 px, puntaje 40 px) | S1 | S-03 |
| 4 | La barra lateral en celular es una tira que **esconde 5 de 8 destinos** (y corta "Grupos" a la mitad) sin ninguna pista de que se desliza. **Ya pasa en `main`** (scrollWidth 1004 px contra 343) y también a 768 px (2 ocultos) | S1 | MS-01, S-05 |
| 5 | Borde de los campos (`--line-strong`) a 1,34:1: viola WCAG 1.4.11 (pide 3:1) | S1 | S-12 (calculado) |
| 6 | Fusión: **12 plantillas en conflicto (30 bloques)**; `grupo.html` solo tiene 9 y es la pantalla más usada | S1 | `07` |
| 7 | Funciones nuevas sin Sereno: 14 templates + `social.css`, `chatbot.css`, JS del chat con clases propias | S1 | `05` §1.6 |
| 8 | Inbox: `.invitation-card` usa tokens inexistentes (`--card-bg`, `--border-color`): **verificado, sin fondo y sin borde** | S1 | C-01 |
| 9 | 27 tokens con el mismo nombre y distinto significado entre el CSS viejo y Sereno (`--accent`, `--surface-2`, `--line`…); el puente actual desaparece en la Fase 7 | S1 | `04` §1 |
| 10 | Paleta de 10 rangos + 3 marcos de racha (53 hex, 377 líneas de CSS dentro de `racha.html`) sin lugar en un sistema casi monocromo | S2 | C-04, C-10, P-04 |
| 11 | Burbujas del chat con hex de respaldo (lima `#d4f55a`, gris `#efefec`, texto `#1a1a1a`), **iguales en claro y en noche**: verificado | S2 | C-02 |
| 12 | Si la fusión se resuelve mal vuelve el `confirm()` nativo (la rama lo trae; `main` ya tiene el diálogo propio) | S1 | C-14 |
| 13 | Componentes duplicados: 17 familias de botón, 3 implementaciones de pestañas, 9 variantes de estado vacío, 26 `<em>` en titulares | S2 | `03`, C-06..C-08 |
| 14 | Textos < 12 px: iniciales de avatar 10 px y badge 11 px (rama); día del calendario 10 px, autor y hora del chat 11,5 y 10,9 px, `.decision-meta` 9 px (`main`) | S2 | S-04, MS-06, M-02 |
| 15b | **Con el texto al 200 % en celular el botón de menú se sale de la pantalla** y aparece scroll horizontal de 29 px en las 28 pantallas medidas (hasta 138 px en perfil público); a 320 px el perfil público también desborda 22 px | S1 | IN-12, IN-11 |
| 15c | Diálogo `preguntar`: el foco inicial está en "Aceptar" incluso al eliminar algo (`Enter` confirma); en 10 de 13 diálogos el foco inicial es "Cerrar"; el foco no vuelve al botón correcto en "Invitar a un grupo" | S2 | IN-01 a IN-03 |
| 15 | Copy de maqueta visible: "Hecho con Inter y Newsreader" en el footer de la rama. Y en `main`: `/inbox` sin `<h1>`, contador del Inbox 3,76:1 | S2 | S-10, MS-02, MS-04 |

## Orden de ataque recomendado (detalle en `06`)

0. **Respaldar la rama** (S). La cuenta de prueba ya se usó (P-00 resuelta).
1. **Fusionar `main`** en una rama nueva `sereno-integracion`, tomando la estructura de `main` y repintando con clases Sereno (M-L).
2. **Corregir los tokens de Sereno antes de propagarlos** (contraste, 44 px, 12 px mínimo): es la fase con mejor relación esfuerzo/impacto (M).
3. Fundaciones que faltan (componentes de `03`) (L).
4. (Opcional) Navegación nueva, **antes** de pintar pantallas.
5. Shell → Inicio y Planes → **Grupos** → Social e Inbox → Perfil, Amigos, Calendario → cierre y borrado de `style.css`.

## Decisiones que necesito de vos (todas en `09-PREGUNTAS.md`)

P-01 congelar funcionalidades · P-02 alturas de control (44/48/52) · P-03 corregir contraste de Sereno · P-04 paleta de rangos · P-05 verde de éxito y rojo destructivo · P-06 hacer o no la fase de navegación · P-07 si hay producción.

## Qué entregué y dónde quedé

| Archivo | Contenido |
|---|---|
| `01-INVENTARIO-PANTALLAS.md` | 33 rutas HTML, parciales, diálogos, matriz de cobertura (qué no se cubrió y por qué) |
| `02-HALLAZGOS.md` | 13 de Sereno, 10 de `main` públicas, 14 de `main` con sesión (MS), 14 de código (3 verificados), descartados, re-verificación |
| `03-COMPONENTES.md` | variantes actuales, mapeo y 11 especificaciones de lo que falta |
| `04-MAPA-DE-TOKENS.md` | viejo → Sereno, huecos, contrastes calculados, hex sueltos |
| `05-DEUDA-DE-CODIGO.md` | CSS, ganchos JS, templates, repositorio |
| `06-PLAN-DE-MIGRACION.md` | 11 fases con criterios medibles, riesgos y tablero |
| `07-PLAN-DE-FUSION.md` | los 12 conflictos reales y cómo resolverlos |
| `08-PLAN-DE-PRUEBAS.md` | herramientas, matriz, 10 flujos críticos |
| `09-PREGUNTAS.md` | decisiones |
| `../../redesign-screens/audit/` | JSON crudos y capturas (22 MB), `INDEX.md`, `herramientas/` |

**Para retomar en otro chat:** lo pendiente es cubrir estados y datos que la cuenta de ejemplo no tiene (invitaciones, encuestas abiertas, mensajes propios, la pestaña Publicaciones del Inbox), teclado en pantalla real, lectores de pantalla y repetir interacción y zoom sobre la rama Sereno. Para repetir las mediciones: `redesign-screens/audit/herramientas/medir_sesion.py` (sesión) y `medir.py` (público), ver `08-PLAN-DE-PRUEBAS.md`.
