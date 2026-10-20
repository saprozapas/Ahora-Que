# 06 — Plan de migración a Sereno

Pensado para ejecutarse **fase por fase**, cada una entregable y verificable sola. Todo se hace en `sereno-integracion` (ver `07-PLAN-DE-FUSION.md`), con el flujo de la memoria del proyecto: nada de ramas de feature ni PRs en `main`; esa rama solo existe para el rediseño y se fusiona una vez al final.

Esfuerzo: **S** ≈ media jornada, **M** ≈ 1-2 jornadas, **L** ≈ 3 o más. Son estimaciones mías sobre el volumen de código contado, no medidas.

**Vara de medición común** (se repite en todas las fases): `medir.py` (el script usado en esta auditoría; hoy está en `redesign-screens/audit/herramientas/`) corrido sobre la pantalla, 8 viewports × 2 temas. Los números de aceptación globales:

| Criterio global | Valor |
|---|---|
| Scroll horizontal (`scrollWidth > clientWidth`) | 0 de 320 a 1920 |
| Objetivos táctiles | 0 menores de 44 px en celular (excepto enlaces dentro de una frase) |
| Contraste de texto | 0 fallos AA (4,5 / 3,0 para grande) en claro y en noche |
| Texto | 0 nodos por debajo de 12 px |
| Colores | 0 hex y 0 `rgb()` fuera de `tokens.css` y de un único bloque `/* RANGOS */` documentado |
| Titulares | 0 `<em>` dentro de `h1-h6`; exactamente 1 `<h1>` por pantalla |
| Alturas de control | 3 valores: 44 / 48 / 52 px en celular (36-40 solo con `pointer: fine`) |
| Tamaños de fuente distintos por pantalla | ≤ 9 |
| Consola | 0 errores de JS, 0 CSS 404 |

---

## Fase 0 — Prerrequisitos
**Alcance:** nada de diseño.
1. Subir `redesign-sereno` a GitHub como rama aparte (`git push origin redesign-sereno`) y hacer un `git bundle` fuera de OneDrive. Hoy la rama existe solo en la compu de Santi.
2. Tener una cuenta de prueba para medir con sesión (ya se usó una de ejemplo en la auditoría; la clave no se guarda en archivos: variables de entorno `AQ_USUARIO`/`AQ_CLAVE`). Si se quieren cubrir invitaciones, encuestas abiertas y moderación, hace falta una cuenta con esos datos.
3. Versionar `redesign-screens/audit/herramientas/` (`medir.py`, `reverificar.py`, `rutas.py`) y dejar `capturar.py` como está.
4. Decidir el congelamiento de funcionalidades (P-01) y las preguntas P-02 a P-06 de `09-PREGUNTAS.md` que bloquean la Fase 2.
5. Sacar los `.pyc` del índice en `main` (commit aparte, `git rm -r --cached __pycache__ models/__pycache__ …`).

**Aceptación:** `git ls-remote --heads origin redesign-sereno` devuelve una línea; P-01 respondida. **Riesgo:** ninguno para el producto. **Esfuerzo:** S.

## Fase 1 — Fusión de `main` (ver `07-PLAN-DE-FUSION.md`)
**Alcance:** 12 templates en conflicto, `app.js`, `base.html`.
**Aceptación:** cero marcadores de conflicto; las 33 rutas HTML responden sin 500; los 10 flujos críticos pasan (`08-PLAN-DE-PRUEBAS.md`); modo noche funciona en una pantalla heredada y en una nueva; se captura el "antes del híbrido" (26 rutas × 375/1440 × 2 temas). **Rollback:** descartar `sereno-integracion`, volver a `redesign-sereno`. **Esfuerzo:** M-L. **Riesgo:** resolución equivocada en `grupo.html` (9 bloques).

## Fase 2 — Arreglar Sereno antes de propagarlo (tipo c)
**Alcance:** `tokens.css`, `components.css`, `brand.css`. Sin tocar templates.
Cambios (de `02-HALLAZGOS.md`): S-01 (`--ink-3`), S-02 (`--ink-4` solo no textual), S-03 (escala de controles 44/48/52 con `--hit`), S-04 (mínimo 12 px en avatar/badge), S-09 (radios), S-12 (borde de controles ≥ 3:1), tokens nuevos de `04-MAPA-DE-TOKENS.md` §3 (`--ok`, rojo destructivo, `--on-photo`, `--scrim-photo`, `--bubble*`), declarar un `@layer` para todo el sistema nuevo, definir el puente que falta (`--on-accent`, `--danger`, `--success`, `--text-*`, `--card-bg`, `--border-color`, `--chat-bubble-*`) para que `social.css`/`chatbot.css` no queden sin tokens.
**Aceptación (medible):** sobre las 14 pantallas heredadas de la rama: contraste 0 fallos en ambos temas; objetivos táctiles <44 → 0 en celular; 0 nodos <12 px; alturas de botón ∈ {44,48,52}. **Verificación:** repetir `medir.py` y comparar contra `sereno-rama/` de esta auditoría (baseline: 13-37 táctiles, 2-38 fallos de contraste, 1-11 textos chicos por pantalla). **Rollback:** `git revert` del commit (solo CSS). **Esfuerzo:** M. **Dependencias:** P-02, P-03, P-05.

## Fase 3 — Fundaciones que faltan
**Alcance:** `components.css`/`brand.css` + una página de muestra `/_componentes` (solo desarrollo) para ver todos los estados. Cada componente según la especificación de `03-COMPONENTES.md` §3: botón danger y de ícono, `.tabs` único, chip de dato y de estado, burbuja de chat, tarjeta de voto, tarjeta de publicación + carrusel + grilla, diálogo largo con pie fijo, esqueleto, toast, estado de error, escala de avatar, paleta de rangos (según P-04).
**Aceptación:** cada componente tiene claro/noche/foco/deshabilitado en la página de muestra; 0 hex salvo `/* RANGOS */`; alturas dentro de la escala. **Esfuerzo:** L. **Rollback:** la página de muestra y el CSS son aditivos; revertir el commit. **Riesgo:** inventar de más: construir solo lo que las fases 6-9 consumen.

## Fase 4 (OPCIONAL, antes de pintar pantallas) — Estructura de navegación
Se habló de: simplificar el menú lateral de 8 entradas, Inicio como centro de acción, unir "Planes" y "Calendario" en "Mis planes", botón "+ Crear" global. **No se mezcla con los hallazgos visuales.** Si se hace: cambia el alcance de las Fases 5-9 (menos plantillas de menú, `planes_menu.html` desaparece, el calendario pasa a pestaña, `_dashboard_sidebar.html` se reduce y S-05 se resuelve de raíz). Si no se hace, S-05 se resuelve con degradado + `scroll-snap`. Decisión en P-06.
**Aceptación:** rutas viejas redirigen (`/planes/` → nueva ruta); 0 enlaces rotos; todos los destinos alcanzables a 375 px sin deslizar. **Esfuerzo:** L. **Riesgo:** alto (cambia URLs y hábitos); es la única fase que puede romper flujos.

## Fase 5 — Shell y navegación
**Alcance:** `base.html`, `_dashboard_sidebar.html`, header, footer, avisos flash, `window.preguntar` (`app.js:773`), diálogos genéricos, `[hidden]`, enlaces de `social.css`/`chatbot.css` movidos al `<head>`, quitar "Hecho con Inter y Newsreader" (S-10), barra de progreso (decidir si vuelve), tira lateral (S-05), `<img>` con tamaño (S-13).
**Dependencias:** Fases 1-3. **Aceptación:** en las 33 rutas, header/sidebar/footer sin hallazgos en `medir.py`; `preguntar` abre, atrapa foco, cierra con `Esc` y devuelve el foco; 0 `<link rel="stylesheet">` en `<body>`. **Esfuerzo:** M. **Riesgo:** todo depende del shell; probar noche y colapso de sidebar.

## Fase 6 — Inicio, Planes
**Alcance (rutas):** `/` (ya hecha en la rama: re-verificar), `/dashboard`, `/explorar`, `/plan/<slug>`, `/planes/*` (7 rutas), `/planes/nueva-idea` (+ el script inline que arma 8 nodos), asistente de planes (`_chatbot_panel`, `chatbot.css` y `chatbot.js`: las 15 clases creadas con `className`).
**Aceptación:** criterios globales + `<h1>` único (S-06); chatbot con burbujas del componente 3.5; chips de datos. **Esfuerzo:** M-L. **Riesgo:** el streaming del asistente depende de clases (`chatbot-transmitiendo`).

## Fase 7 — Grupos (la más grande y la más usada)
**Alcance:** `/grupos`, `/grupos/nuevo`, `/grupos/<id>` (cabecera, tablero, encuestas, modales ×4), `/grupos/<id>/chat`, `/postular`, `/asistente`, `/encuestas/nueva`, `/racha/<id>`.
Orden interno: lista → nuevo → cabecera y pestañas → tablero y tarjeta de voto → encuestas → modales → chat → postular/asistente → racha (último por la paleta de rangos y el `<style>` inline de 377 líneas, P-04).
**Aceptación:** criterios globales por ruta; el tablero muestra los 5 estados con datos reales; el chat agrupa mensajes y no usa `#efefec/#d4f55a`; `racha.html` sin `<style>` en el template. **Esfuerzo:** L. **Riesgo:** `grupo.html` (585 líneas, 9 bloques de conflicto); los formularios de voto no deben perder `name`/`value`.

## Fase 8 — Social e Inbox
**Alcance:** `/social` (3 pestañas, feed, descubrir, actividad), diálogos (compartir, proponer, reportar), `/social/p/<id>`, `/social/moderacion`, grilla de "Planes publicados" en `/perfil` y `/usuarios/<id>`, `/inbox` (pestañas, avisos, contadores).
**Aceptación:** criterios globales; foto 4:5 única; me gusta con `aria-pressed`; diálogo de compartir alcanzable en 320×640; sin `--card-bg` indefinido (C-01); `social.css` sin referencias a tokens viejos (`grep -c 'var(--muted\|--surface-1\|--text-'` = 0). **Esfuerzo:** M-L. **Riesgo:** bajo en JS (`data-soc-*`), medio en el feed (CLS al cargar por `fetch`).

## Fase 9 — Perfil, Amigos, Calendario y páginas estáticas
`/perfil`, `/perfil/cambiar-contrasena`, `/amigos`, `/calendario`, `/contacto`, `/register`, `/login`. Gran parte ya está hecha en la rama: re-medir y cerrar. **Esfuerzo:** S-M.

## Fase 10 — Cierre ("Fase 7" original)
1. Borrar `static/style.css` y el puente de `brand.css` §01. 2. Con `grep`, borrar clases muertas confirmadas (C-13). 3. Pasar los 26 `<em>` de titulares a texto con peso (C-08). 4. Capturas finales antes/después con `capturar.py` (26+7 rutas × 375/1440 × claro/noche). 5. Actualizar `README.md`. 6. Regresión completa (`08-PLAN-DE-PRUEBAS.md`). 7. Etiqueta `pre-sereno` en `main`, merge `--no-ff`.
**Aceptación:** `style.css` no existe y ninguna ruta pierde estilo (diff de capturas); criterios globales en las 33 rutas; 0 `var(--…)` sin definir (`grep` cruzado entre usos y definiciones).
**Rollback:** `git reset --hard pre-sereno` local; si hay despliegue, redeploy de la etiqueta (P-07).

---

## Orden y dependencias

`F0 → F1 → F2 → F3 → (F4 opcional) → F5 → F6 → F7 → F8 → F9 → F10`. F6, F7, F8 y F9 son independientes entre sí una vez hechas F2, F3 y F5; podrían ir en paralelo en sesiones distintas si no tocan los mismos archivos (grupo ↔ social comparten `_social_plantillas` solo en Perfil).

Prioridad por impacto × dependencia × riesgo: shell (todo depende) → Grupos (lo más usado y con más defectos) → Planes/Inicio → Social/Inbox → Perfil/Amigos/Calendario → estáticas.

## Plan de riesgos por fase (resumen)

| Fase | Riesgo principal | Mitigación | Rollback |
|---|---|---|---|
| 0 | Pérdida de la rama | Push + bundle | — |
| 1 | Resolver mal `grupo.html` | Tomar main, repintar; 10 flujos | Descartar `sereno-integracion` |
| 2 | Tokens cambian toda la app | Medir antes/después | Revertir commit |
| 3 | Sobre-construir | Solo lo que consumen F6-F9 | Revertir (aditivo) |
| 4 | Romper URLs | Redirecciones | Revertir fase |
| 5 | Shell afecta todo | Probar claro/noche/colapsada | Revertir |
| 6-9 | Perder clases que usa el JS | Lista de ganchos de `05-DEUDA-DE-CODIGO.md` §2 | Revertir por pantalla |
| 10 | Quedan reglas viejas necesarias | Diff de capturas antes de borrar | Etiqueta `pre-sereno` |

---

## Tablero de avance

| Fase | Estado | Fecha | Notas |
|---|---|---|---|
| 0 Prerrequisitos | pendiente | | |
| 1 Fusión de `main` | pendiente | | |
| 2 Arreglar Sereno (tokens) | pendiente | | |
| 3 Fundaciones que faltan | pendiente | | |
| 4 Navegación (opcional) | pendiente | | Depende de P-06 |
| 5 Shell y navegación | pendiente | | |
| 6 Inicio y Planes | pendiente | | |
| 7 Grupos | pendiente | | |
| 8 Social e Inbox | pendiente | | |
| 9 Perfil, Amigos, Calendario, estáticas | pendiente | | |
| 10 Cierre | pendiente | | |
