# 07 — Plan de fusión de `main` en `redesign-sereno`

Resultado de **probar la fusión de verdad** en un worktree descartable (`git worktree add --detach C:/tmp/mg redesign-sereno` y `git merge --no-commit --no-ff main`). No se commiteó nada y el worktree se borra al terminar la auditoría. Fecha: 2026-10-20.

## 1. Números reales

| | Rama `redesign-sereno` | `main` |
|---|---:|---:|
| Commits desde la base (`9eea1fa`) | 12 | 59 |
| Archivos tocados (sin `.pyc`) | 84 (+4.219 / −2.272) | 81 (+17.319 / −985) |
| Archivos tocados por **ambos** lados | 14 | |
| Conflictos de texto | **12 archivos, 30 bloques** | |
| Archivos que llegan solo desde `main` | 72 (backend, servicios, migraciones, 14 templates, `social.css`, `chatbot.css`, JS) | |

Archivos con conflicto y cantidad de bloques: `grupo.html` 9, `social.html` 3, `grupos.html` 3, `base.html` 2, `inbox.html` 2, `grupo_postular.html` 2, `planes_nuevo.html` 2, `amigos.html` 1, `perfil.html` 1, `plan_detalle.html` 1, `planes_lista.html` 1, `planes_menu.html` 1.

Cambiados por ambos pero **sin conflicto** (git los unió solo; hay que revisar que el resultado tenga sentido): `static/app.js`, `templates/perfil_publico.html`. Ojo con `app.js`: la rama le borró 118 líneas (barra de progreso de scroll y aparición de secciones) y `main` le agregó 52 (diálogo `preguntar`, avisos). El texto se une, pero hay que comprobar en el navegador que `window.preguntar`, el reordenado de la barra lateral y `data-confirmar` siguen funcionando.

Sin conflicto de texto no significa "funciona": 14 templates de `main` (`_chatbot_panel`, `_social_iconos`, `_social_perfil`, `_social_plantillas`, `grupo_asistente`, `grupo_cabecera`, `grupo_chat`, `grupo_encuesta_nueva`, `grupo_encuestas`, `grupo_modales`, `planes_asistente`, `racha`, `social_moderacion`, `social_publicacion`) entran intactos con clases viejas. Siguen viéndose gracias a que `style.css` se sigue cargando, pero con tokens remapeados por el puente (ver `04-MAPA-DE-TOKENS.md` §1).

## 2. Estrategia recomendada

Tres opciones evaluadas:

| Opción | Costo | Riesgo | Veredicto |
|---|---|---|---|
| A. `git merge main` dentro de la rama y resolver los 12 conflictos | 30 bloques, ~1 día de trabajo cuidadoso | Medio: errores de resolución silenciosos en `grupo.html` | **Recomendada**, con la regla de resolución de la sección 3 |
| B. `git rebase main` | Los 12 commits se reaplican uno por uno: los mismos archivos conflictúan varias veces (`grupo.html` pasó por Fase 5 y Fase 6) | Alto: conflictos repetidos | Descartada |
| C. Rama nueva desde `main`, copiar `static/css/*` y reaplicar pantalla por pantalla | Reescribe a mano lo que la rama ya hizo en las ~30 pantallas heredadas | Bajo en riesgo, alto en horas | Solo para los 14 templates nuevos (ya es la Fase 3 del plan) |

Pasos de la opción A:
1. **Respaldar**: `git push origin redesign-sereno` (rama aparte, no toca `main`; hoy no existe en GitHub). También `git bundle create sereno.bundle redesign-sereno main` en un disco fuera de OneDrive.
2. Crear `sereno-integracion` desde `redesign-sereno` (no trabajar sobre la rama original).
3. Fusionar `main` con `git merge main`, en un worktree en ruta corta (`C:/tmp/...`).
4. Resolver los 12 archivos según la sección 3.
5. Quitar del índice los `.pyc` (commit aparte) para que no ensucien.
6. Levantar la app con la base real (login de Santi) y recorrer los 10 flujos críticos de `08-PLAN-DE-PRUEBAS.md`. Punto estable: **sitio híbrido** (Sereno en pantallas heredadas, estilo viejo con tokens puenteados en las nuevas).
7. Recién ahí empezar las fases de pantalla (`06-PLAN-DE-MIGRACION.md`).

Congelamiento: mientras dure la fusión y hasta terminar la fase de fundaciones conviene **no agregar pantallas nuevas en `main`**. Cada template nuevo que entre con estilo viejo suma trabajo (hoy son 14 y la cuenta ya es grande). Si hay que agregar funciones: respetar las tres reglas de la memoria (CSS en bloque propio y con tokens, `data-*` para JS, cero `<em>` en titulares).

## 3. Regla de resolución y detalle por archivo

**Regla general**: en cada bloque en conflicto, quedarse con la **estructura y la lógica de `main`** (backend y JS dependen de ella: `data-confirmar`, `data-soc-*`, formularios, nombres de campos, `url_for`) y volver a aplicar sobre esa estructura las **clases de Sereno** de la rama. Nunca al revés: la rama es anterior a 59 commits de funcionalidad.

| Archivo | Bloques | Qué hizo cada lado | Resolución |
|---|---:|---|---|
| `templates/base.html` | 2 | Solo cambió el número de versión del `style.css` y `app.js` (`20260929-sereno-f6d` vs `20261014-admin-grupo-v13`) | Tomar la rama (carga `css/tokens.css`, `components.css`, `brand.css`, `pages.css` y las fuentes Inter/Newsreader) y subir el sufijo de versión. Decidir si `social.css` y `chatbot.css` se enlazan desde `<head>` (recomendado; hoy están en el `<body>`). |
| `templates/amigos.html` | 1 | Rama: `<form class="form-eliminar-amigo">` con clases Sereno. Main: acciones dentro de `.friend-card-actions` y `data-confirmar` (ya está en ambos) | Estructura de main; clases Sereno de la rama. Verificar el modal "Invitar a un grupo" (usa `onclick … .close()` y `<dialog>`). |
| `templates/perfil.html` | 1 | Rama: fila `profile-row` con enlace `btn btn--ghost btn--sm`. Main: `<p><strong>Contraseña</strong>` + enlace plano | Rama (es solo estilo). Main agrega la grilla "Planes publicados" y `_social_perfil.html`: conservar. |
| `templates/plan_detalle.html` | 1 | Rama: `onsubmit="return confirm(...)"` nativo. Main: `data-confirmar="..."` | **Main** (diálogo propio). La rama no conoce `preguntar`. |
| `templates/planes_lista.html` | 1 | Rama: línea `plan-tile__meta`. Main: botón "quitar de guardados" (`mostrar_quitar_guardado`, `data-confirmar`) | Unir: meta de la rama + formulario de main. |
| `templates/planes_menu.html` | 1 | Rama: `<ul class="menu-list">`. Main: `<a class="planes-menu-tile">` con SVG | Estructura de main (nuevas entradas), clases de lista de accesos de Sereno (sección 20 de `brand.css`). |
| `templates/planes_nuevo.html` | 2 | (1) cabecera `page-head` vs `auth-intro` con `<em>`. (2) JS inline: `inputHora.className = "input planner-stop__time"` vs `"crear-plan-elegido-campo"` + `if (hora) {…}` | (1) rama. (2) **unir a mano**: la clase de la rama + la línea `if (hora)` de main; el JS inline arma 8 nodos con clases `crear-plan-*` que el CSS de Sereno (`planner-stop__*`) nombra distinto: revisar todas. |
| `templates/grupo_postular.html` | 2 | Cabecera (`page-head`/`h1.h2` vs `auth-intro` con `<em>`) y estado vacío (`empty-state` vs `group-board-empty` con botón al asistente) | Rama para la cabecera; **main** para el estado vacío porque agrega el botón al asistente. |
| `templates/inbox.html` | 2 | Rama rediseñó el Inbox viejo. Main agregó pestañas Solicitudes/Publicaciones, avisos y 176 líneas nuevas (`group-tabs inbox-tabs`) | **Main entero** y reaplicar Sereno (es una pantalla nueva en la práctica). |
| `templates/social.html` | 3 | Rama: macro `avatar` y cabecera de la lista vieja. Main: reescritura completa (feed, pestañas, diálogos) | **Main entero**; la rama no aporta (su versión es la "Actividad" vieja). |
| `templates/grupos.html` | 3 | Main agrega racha, marcos de insignia y el macro con 4 parámetros (`group, numero, enlazable, racha`). La rama convirtió la tarjeta en `card plan-tile group-tile` | Main (macro y datos de racha) + clases Sereno de la tarjeta. |
| `templates/grupo.html` | 9 | La rama rehízo el tablero (`board__section`, 5 secciones, `empty-state`); main reescribió la cabecera, el tablero por estado, el chat y el modal "Invitar" (585 líneas, 173+79+123+114+162 líneas nuevas en los bloques) | **El más delicado.** Tomar main bloque por bloque y volver a pintar con `board__*`/`card`/`btn` de la rama. No intentar mezclar líneas: copiar el bloque de main y cambiar clases. |

Orden recomendado de resolución: `base.html` → `planes_menu` → `planes_lista` → `plan_detalle` → `perfil` → `amigos` → `grupo_postular` → `planes_nuevo` → `grupos` → `inbox` → `social` → `grupo`. Es de menor a mayor riesgo, así los errores de criterio se cometen primero donde son baratos.

## 4. Verificación después de la fusión (antes de tocar diseño)

- `git diff --name-only --diff-filter=U` vacío y ningún marcador `<<<<<<<` en el árbol: `grep -rn '^<<<<<<<\|^>>>>>>>' templates static`.
- La app arranca y las 33 rutas con HTML de `01-INVENTARIO-PANTALLAS.md` responden sin 500 con la cuenta de prueba.
- `window.preguntar` abre el diálogo propio en: eliminar amigo, bajarse de un plan, quitar de guardados, cerrar votación.
- Hay una sola copia de cada `<script>` (`app.js` no se carga dos veces tras la unión automática).
- Modo noche sigue funcionando en una pantalla heredada y en una nueva (el puente de tokens).
- Mediciones de referencia de la sección C del método sobre `/grupos/<id>` y `/social` para tener un "antes" del híbrido.

## 5. Riesgos y rollback

- **Pérdida de la rama**: hoy existe solo en la compu de Santi. Mitigación: paso 1.
- **Resolución silenciosamente equivocada** (se conserva el lado viejo de un bloque): mitigación, recorrer los 10 flujos y comparar con capturas del `main` actual.
- **Rollback**: la fusión se hace en `sereno-integracion`; si sale mal se descarta la rama y se vuelve a `redesign-sereno` intacta. `main` no se toca hasta el final.
- **Merge final a `main`**: se hace al terminar la Fase 7, con `git merge --no-ff` y una etiqueta (`pre-sereno`) en `main` antes de fusionar, para volver con un `git reset --hard pre-sereno` local si algo falla en producción (hay que confirmar con Santi si hay un despliegue: ver `09-PREGUNTAS.md`).
