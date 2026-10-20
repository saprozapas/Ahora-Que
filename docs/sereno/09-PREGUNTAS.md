# 09 — Decisiones que necesito de vos

Todas juntas, con opciones y mi recomendación. Las marcadas **(bloquea)** frenan una fase concreta.

| ID | Pregunta | Opciones | Recomendación | Bloquea |
|---|---|---|---|---|
| ~~P-00~~ | **Resuelta**: pasaste una cuenta de ejemplo y se midieron 30 pantallas con sesión (la clave no quedó en ningún archivo). Para cubrir lo que falta (invitaciones, encuestas abiertas, mensajes propios, moderación) haría falta una cuenta con esos datos o un permiso explícito para crearlos. | — | — | — |
| **P-01** | ¿Se congelan las funcionalidades nuevas en `main` durante la migración? Hoy hay 14 templates nuevos con estilo viejo y cada pantalla nueva suma trabajo. | (a) congelar desde la Fase 1 hasta terminar la Fase 3; (b) seguir, pero respetando las 3 reglas (CSS en bloque, `data-*`, sin `<em>`); (c) no congelar | (a) corto: solo hasta la Fase 3. Después, nuevas pantallas ya nacen en Sereno. | Fase 0 |
| **P-02** | Alturas de control. El prompt original pide a la vez "alturas únicas 40/44/48" y "todo ≥ 44 px". Sereno trae 34/42/50. | (a) 44 / 48 / 52 en celular y 36-40 con puntero fino; (b) 40 / 44 / 48 aceptando que 40 no cumple 44; (c) 44 en todas partes | (a) | Fase 2 |
| **P-03** | Contraste de Sereno. Para llegar a AA hay que oscurecer `--ink-3` (≈ `#696964`) y dejar `--ink-4` solo para no-texto. Cambia levemente la estética "aireada" del sistema original. | (a) corregir los tokens (recomendado); (b) mantener Sereno exacto y aceptar fallos AA; (c) corregir solo texto de cuerpo y dejar el meta en ink-4 | (a) | Fase 2 |
| **P-04** | **Paleta de rangos de la racha** (10 títulos de colores + 3 marcos). Sereno es casi monocromo. | (a) mantener los colores en un único bloque `/* RANGOS */` documentado como excepción; (b) pasar a una escala monocromática con forma/ícono para distinguir; (c) simplificar a 3-4 rangos | (a) ahora, (b) como mejora posterior. Es identidad gamificada que ya gusta. | Fase 3 y 7 |
| **P-05** | **Éxito y destructivo.** Sereno no tiene verde de éxito y reserva el rojo para "urgencia real". Hoy "Abandonar", "Eliminar" y los errores usan rojo; "Confirmado" y "Aceptar" usan verde. | (a) agregar `--ok` y `--danger` como tokens de Sereno (verde y rojo apagados); (b) todo en tinta + ícono, sin color; (c) solo `--alert` para todo | (a), con ambos apagados y siempre acompañados de texto o ícono | Fase 2 |
| **P-06** | **Navegación.** ¿Se hace la Fase 4 (menú de 8 a ~4, Inicio como centro de acción, "Mis planes" = Planes + Calendario, botón "+ Crear")? | (a) no, solo arreglar la tira lateral de celular (S-05); (b) sí, antes de pintar pantallas; (c) sí, después de terminar la migración visual | (b) si la querés de todos modos: hacerla después significa pintar dos veces. Si no estás seguro, (a). | Fase 4 |
| **P-07** | ¿Hay despliegue en producción? ¿Quién usa la app hoy además del equipo? Define el rollback del merge final. | (a) solo local/demo; (b) hay un despliegue con usuarios | Confirmar cuál es. | Fase 10 |
| **P-08** | Contador del Inbox en la barra lateral: hoy rojo `#ef4444`. ¿Cuenta como "urgencia real"? | (a) `--alert` rojo; (b) `--accent` o tinta con punto; | (b): un aviso pendiente no es urgencia | Fase 5 |
| **P-09** | Fuentes: Sereno usa Inter + Newsreader; `main` Figtree + Fraunces + JetBrains Mono. ¿Se mantiene el cambio de familia (y el serif para "voz humana")? | (a) Sereno completo; (b) mantener Fraunces/Figtree con la escala de Sereno | (a): el sistema ya se probó así en 12 commits | Fase 2 |
| **P-10** | La barra de progreso de scroll y la aparición de secciones al scrollear (`scroll-reveal`) se eliminaron en la rama. ¿Quedan fuera para siempre? | (a) fuera (más estable, mejor accesibilidad e impresión); (b) volver con `prefers-reduced-motion` | (a) | Fase 5 |
| **P-11** | `__pycache__/*.pyc` versionados (71 en `main`). ¿Los saco del índice? Es un commit aparte, no del rediseño. | (a) sí, ahora; (b) más adelante | (a) en la Fase 0 | — |

## Dónde quedó la auditoría

Hecho: reconocimiento completo (rutas, parciales, hojas, JS), medición de las **páginas públicas de `main`**, de **30 pantallas con sesión de `main`** (datos reales) y de **14 pantallas de la rama Sereno** (datos simulados), auditoría de código, mapa de tokens, plan de fusión probado en un worktree, plan de migración, plan de pruebas y re-verificación.
También se midieron interacción (foco, `Esc`, diálogos, carrusel) y zoom sobre `main` (`02-HALLAZGOS.md` §C2).
Falta: estados que la cuenta de ejemplo no tiene, `/inbox?tab=publicaciones` (escribe), teclado en pantalla real, lectores de pantalla y repetir interacción y zoom sobre la rama Sereno.
