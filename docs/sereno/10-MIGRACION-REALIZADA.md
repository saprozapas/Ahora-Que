# Migración a Sereno — qué se hizo y cómo se verificó

Rama: `sereno-integracion` (local, **sin push**). Parte de `origin/main` + `redesign-sereno`.
`main` no se tocó. Todo el comportamiento de `main` se conserva; cambia solo el estilo.

## Decisiones tomadas (respuestas del equipo)

| Tema | Decisión |
|---|---|
| Títulos de racha | Monocromo, con ícono + nombre |
| Marcos de racha | Ocultos, junto con su selector. Se rediseñan más adelante |
| Éxito / peligro | Tokens `--ok` y `--danger` apagados (más `-soft`, `--on-danger`) |
| Navegación móvil | Se arregla la tira, manteniendo la estructura (degradé + snap) |
| Contraste | Todo a AA (`--ink-3` ≥ 4,94:1; bordes de control 3:1) |
| Tipografías | Se mantienen Figtree y Fraunces |

## Qué cambió

- **Sistema**: `tokens.css`, `components.css`, `brand.css`, `pages.css` + nuevos `grupos.css`, `social.css`, `chatbot.css`. `static/style.css` y el puente de tokens viejos **se eliminaron**.
- **Escala de controles**: 44/48/52 px en pantallas táctiles o angostas; 40/44/48 con puntero fino a partir de 901 px.
- **Pantallas pasadas a Sereno**: grupo (tablero, cabecera, modales, encuestas, chat, asistente), grupos, racha, inbox, social (amigos, descubrir, actividad, publicación, moderación, perfiles), registro, términos, cambiar contraseña, asistentes de ideas, panel del chatbot.
- **JS**: `iniciarModales` (foco inicial, vuelta al disparador), `preguntar()` como `alertdialog` con foco en Cancelar, menús desplegables que cierran con Esc / clic afuera, tira de navegación, carrusel de fotos accesible.
- **Fusión con main**: se resolvieron los conflictos de plantillas conservando la estructura y las funciones de main (`data-confirmar`, `hora` en nueva idea, rachas, social).

## Verificación (build local contra la base compartida)

| Chequeo | Resultado |
|---|---|
| Paridad funcional vs main (38 rutas: enlaces, formularios, controles, ids, data-attrs) | Todas responden 200. Dos diferencias intencionales: enlace del landing a un plan de ejemplo y el filtro de precio del planificador (ahora radios) |
| Contraste, rutas con sesión, 375 y 1440, claro y noche (124 mediciones) | **0 fallos** |
| Texto menor a 12 px | **0** |
| Scroll horizontal (320 / 375 / 768 / 1440) | **0** |
| Texto al 200 % en celular (6 pantallas desbordaban) | Corregido: **0** desbordes |
| Diálogos a 375 px: foco inicial, trampa de foco, Esc, foco de vuelta, clic afuera | Correcto en 13 de 15 casos; los otros 2 (cerrar votación y ver comentarios) no se pudieron disparar con los datos de la cuenta de prueba |
| Objetivos táctiles < 44 px a 375 px | Solo quedan el *skip link* (fuera de pantalla), el enlace estirado de la tarjeta (toda la tarjeta es clicable) y radios dentro de etiquetas de 44 px |
| Flujos con escritura (20 pasos, datos «ZZ Sereno») | 17 de 20 OK; ver abajo |

### Flujos con escritura
Crear grupo, cabecera y pestañas, modal Invitar (sin invitar), modal Editar, chat, crear idea, racha, publicar en social con me gusta / comentario / guardar, encuesta, panel del asistente, y borrado de publicación, plan, idea y grupo: **OK**.

**Pasos 8–10 (votar y cerrar la votación)** no se pudieron recorrer: con un grupo de una sola persona, el plan postulado queda directamente en «Confirmados». Las rutas de backend son idénticas a main, así que es comportamiento previo, no una regresión. **Falta probar votar y cerrar con 2 o más integrantes** (requiere otra cuenta).

### Limpieza de la base
Los flujos dejaron 2 ideas «ZZ Sereno» (con sus filas en `Usuario-Plan`, `Plan_Lugar` y `Publicacion`). Se borraron con `limpieza_bd.py` (solo filas con ese prefijo); un recuento final dio 0 grupos y 0 planes de prueba. El grupo de prueba se eliminó solo al abandonarlo su única integrante.

## Pendiente / a tener en cuenta

1. **Marcos de racha**: ocultos a propósito. Hay que diseñarlos y volver a mostrarlos.
2. **Votación con 2+ integrantes**: probar a mano o con una segunda cuenta de prueba.
3. **Contraseña de la base**: sigue visible en el historial de `origin/main`. Conviene rotarla.
4. **Límite de intentos de login** (5 en 30 min, cuenta todos los intentos): mis mediciones bloquearon unos 30 min la cuenta de prueba. Las herramientas ahora reutilizan una sesión guardada.
5. **`/usuarios/<id>` muestra el correo** de la persona. Es comportamiento de main; vale la pena revisar si debe ser público.
6. Las capturas con nombres reales **no se versionan** (están solo en carpetas locales).
7. Integrar: cuando se decida, `sereno-integracion` se fusiona en `main` (no se hizo).

## Herramientas (en `redesign-screens/herramientas/`)
`medir.py`, `medir_sesion.py`, `interaccion_sesion.py`, `paridad.py`, `resumir_sesion.py`, `rutas.py`, `flujos.py`, `limpieza_bd.py`. Las credenciales se pasan por variables de entorno o por un archivo de sesión temporal; nunca se escriben en el repositorio.
