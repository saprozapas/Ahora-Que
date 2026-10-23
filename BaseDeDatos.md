Esta es la base de datos del proyecto

## Table `Usuarios`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Nombre` | `text` |  |
| `Mail` | `text` |  Nullable Unique |
| `Fecha_Nac` | `date` |  Nullable |
| `Id_Usuario` | `uuid` | Primary |
| `Password_Hash` | `text` |  Nullable |
| `Username` | `text` |  Nullable Unique |
| `Descripcion` | `text` |  Nullable |

## Table `Lugar`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Apto_Menores` | `bool` |  Nullable |
| `Id_Lugar` | `uuid` | Primary |
| `Lat` | `numeric` |  Nullable |
| `Long` | `numeric` |  Nullable |
| `Nombre` | `text` |  Nullable |
| `Opcion_Celiacos` | `bool` |  Nullable |
| `Opcion_Vegana` | `bool` |  Nullable |
| `Ambiente` | `text` |  Nullable |
| `Direccion` | `text` |  Nullable |
| `Nivel_Precio` | `int4` |  Nullable. Check: 0 a 5. Categoría de precio: 0 Gratis · 1 `$` (100 a 300 pesos) · 2 `$$` (300 a 600) · 3 `$$$` (600 a 1000) · 4 `$$$$` (1000 a 2000) · 5 `$$$$$` (más de 2000). Los montos están en `services/precio_lugar.py`; NULL = sin dato |
| `Imagen_Url` | `text` |  Nullable |
| `Osm_Id` | `text` |  Nullable Unique. Id en OpenStreetMap (`node/123`, `way/456`, `relation/789`); lo usa `scripts/importar_osm.py` |
| `Fuente` | `text` | Default `'manual'`. `'osm'` si vino de OpenStreetMap |
| `Verificado` | `bool` | Default `false`. `true` = corregido a mano: la importación de OSM no lo pisa |
| `Barrio` | `text` |  Nullable. Nombre tal cual lo da OSM |
| `Precio_Origen` | `text` | Nullable. Check: `'marca'`, `'cocina'`, `'nombre'`, `'tipo'` o `'manual'`. De dónde salió `Nivel_Precio`: `marca` cadena o lugar conocido, `cocina` etiqueta de OpenStreetMap, `nombre` palabras del nombre, `tipo` lo normal para ese tipo de lugar (la menos confiable), `manual` lo puso una persona (`scripts/estimar_precios.py` nunca lo pisa). NULL = no es una estimación (gratis cargados con la importación) o sin precio |

## Table `Plan`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Fecha` | `date` |  Nullable |
| `Hora` | `time` |  Nullable |
| `Precio` | `numeric` |  Nullable |
| `Grupo_id` | `uuid` |  Nullable |
| `id_Plan` | `uuid` | Primary |
| `Lugar_id` | `uuid` |  Nullable |
| `Nombre` | `text` |  |
| `Creado_Por` | `uuid` |  Nullable |
| `Estado` | `text` |  Nullable |
| `Descripcion` | `text` |  Nullable |
| `Precio_Min` | `numeric` |  Nullable |
| `Precio_Max` | `numeric` |  Nullable |

## Table `Grupos`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Creado_Por` | `uuid` |  |
| `Nombre` | `text` |  |
| `Id_Grupo` | `uuid` | Primary |
| `Descripcion` | `text` |  Nullable |
| `Todos_Admin` | `boolean` | Default `false`. Si está activo, todo el que entra al grupo es admin |

## Table `Rachas`

Una fila por grupo. Se actualiza al abrir el grupo, usando los planes grupales
que ya ocurrieron. `Semanas` cuenta las semanas con reunión dentro de la racha;
una semana sin reunión la pausa, y 14 días sin reunirse la reinician.

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Grupo` | `uuid` | Primary, Foreign Key → `Grupos.Id_Grupo` (`ON DELETE CASCADE`) |
| `Activa` | `boolean` | Not Null, Default `false` |
| `Semanas` | `int4` | Not Null, Default `0` |
| `Ultima_Reunion` | `date` | Nullable |
| `Ultimo_Plan_Procesado` | `timestamp` | Nullable. Punto de control: los planes anteriores ya fueron contabilizados |
| `Planes_Hechos` | `int4` | Not Null, Default `0`. Acumulado independiente de los planes que sigan en `Plan` |

## Table `Grupo_Insignia`

Guarda los hitos ganados permanentemente por cada grupo, aunque la racha
actual se reinicie. Cada semana objetivo se registra una sola vez.

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Grupo` | `uuid` | Primary, Foreign Key → `Grupos.Id_Grupo` (`ON DELETE CASCADE`) |
| `Semanas` | `int4` | Primary. Hito: 3, 5, 10, 20, 30, 40, 50, 70, 90 o 100 |
| `Desbloqueado_En` | `timestamptz` | Not Null, Default `now()` |

Para crear esta tabla en Supabase:

```sql
CREATE TABLE IF NOT EXISTS public."Grupo_Insignia" (
    "Id_Grupo" uuid NOT NULL
        REFERENCES public."Grupos" ("Id_Grupo") ON DELETE CASCADE,
    "Semanas" integer NOT NULL
        CHECK ("Semanas" IN (3, 5, 10, 20, 30, 40, 50, 70, 90, 100)),
    "Desbloqueado_En" timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("Id_Grupo", "Semanas")
);
```

La apariencia elegida por el grupo se guarda aparte de los premios ganados:

```sql
CREATE TABLE IF NOT EXISTS public."Grupo_Apariencia" (
    "Id_Grupo" uuid PRIMARY KEY
        REFERENCES public."Grupos" ("Id_Grupo") ON DELETE CASCADE,
    "Marco_Semanas" integer NULL,
    "Titulo_Semanas" integer NULL,
    CHECK ("Marco_Semanas" IS NULL OR "Marco_Semanas" IN (3, 10, 30, 70, 100)),
    CHECK ("Titulo_Semanas" IS NULL OR "Titulo_Semanas" IN (3, 5, 10, 20, 30, 40, 50, 70, 90, 100))
);
```

La aplicación valida que los hitos seleccionados estén desbloqueados en
`Grupo_Insignia` antes de guardar la apariencia.

Para actualizar una tabla `Rachas` que ya existe en Supabase:

```sql
ALTER TABLE public."Rachas"
    ADD COLUMN IF NOT EXISTS "Ultimo_Plan_Procesado" timestamp without time zone,
    ADD COLUMN IF NOT EXISTS "Planes_Hechos" integer NOT NULL DEFAULT 0;
```

## Table `Usuario-Grupo`

Conecto Usuarios con Grupos

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Usuario` | `uuid` | Primary |
| `Id_Grupo` | `uuid` | Primary |
| `Es_Admin` | `boolean` | Default `false`. Lo pone el trigger `usuario_grupo_es_admin` al insertar |
| `Fecha_Union` | `timestamptz` | Default `now()`. Desempata la sucesión de admin |

## Table `horario_lugar`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `lugar_id` | `uuid` |  |
| `dia_semana` | `int4` |  |
| `hora_apertura` | `time` |  |
| `hora_cierre` | `time` |  |

## Table `Usuario-Plan`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Usuario_id` | `uuid` | Primary |
| `Plan_id` | `uuid` | Primary |
| `Confirmado` | `bool` |  Nullable |
| `Guardado` | `bool` |  |
| `Puntaje` | `int2` |  Nullable |

## Table `Tipo`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Tipo` | `int4` | Primary |
| `Nombre` | `varchar` |  Unique |

## Table `Lugar_Tipo`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Lugar_id` | `uuid` | Primary |
| `Tipo_id` | `int4` | Primary |

## Table `gasto`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id_gasto` | `uuid` | Primary |
| `plan_id` | `uuid` |  |
| `descripcion` | `text` |  |
| `monto_total` | `numeric` |  |
| `pagado_por` | `uuid` |  |

## Table `gasto_detalle`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id_detalle` | `uuid` | Primary |
| `gasto_id` | `uuid` |  |
| `usuario_id` | `uuid` |  |
| `monto_debe` | `numeric` |  |

## Table `Invitaciones`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Usuario` | `uuid` | Primary |
| `Id_Grupo` | `uuid` | Primary |
| `Mensaje` | `text` |  Nullable |
| `Nombre_invitante` | `text` |  |

## Table `Plan_Lugar`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Plan_Lugar` | `uuid` | Primary |
| `Id_Plan` | `uuid` |  |
| `Id_Lugar` | `uuid` |  Nullable |
| `Nombre` | `text` |  |
| `Precio` | `numeric` |  Nullable |
| `Hora` | `time` |  Nullable |
| `Orden` | `int4` |  |
| `Precio_Min` | `numeric` |  Nullable |
| `Precio_Max` | `numeric` |  Nullable |

## Table `Amistades`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Usuario1` | `uuid` | Primary |
| `Id_Usuario2` | `uuid` | Primary |
| `Fecha_Creacion` | `timestamptz` |  |

## Table `Solicitudes_Amistad`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Solicitante` | `uuid` | Primary |
| `Id_Destinatario` | `uuid` | Primary |
| `Fecha` | `timestamptz` |  |

## Table `Plan_Voto`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Plan` | `uuid` | Primary |
| `Id_Usuario` | `uuid` | Primary |
| `Me_Gusta` | `bool` |  |
| `Puedo` | `bool` |  |
| `Fecha` | `timestamptz` |  |

## Table `Plan_Horario`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Horario` | `int8` | Primary Identity |
| `Id_Plan` | `uuid` |  |
| `Propuesto_Por` | `uuid` |  |
| `Fecha` | `date` |  |
| `Hora` | `time` |  |
| `Estado` | `text` |  |
| `Creado` | `timestamptz` |  |

## Table `Plan_Horario_Voto`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Horario` | `int8` | Primary |
| `Id_Usuario` | `uuid` | Primary |
| `Puedo` | `bool` |  |

## Table `Mensajes`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Grupo` | `uuid` |  |
| `Id_Mensaje` | `uuid` | Primary |
| `Id_Usuario` | `uuid` |  |
| `Contenido` | `text` |  |
| `Fecha_Envio` | `timestamp` |  |

## Table `Conversacion`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Conversacion` | `uuid` | Primary |
| `Tipo` | `text` |  |
| `Dek_Cifrada` | `bytea` |  |
| `Created_At` | `timestamptz` |  |
| `Id_Grupo` | `uuid` |  Nullable |
| `Id_Usuario_A` | `uuid` |  Nullable |
| `Id_Usuario_B` | `uuid` |  Nullable |

## Table `Conversacion_Miembro`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Conversacion` | `uuid` | Primary |
| `Id_Usuario` | `uuid` | Primary |

## Table `Mensaje`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Mensaje` | `uuid` | Primary |
| `Id_Conversacion` | `uuid` |  |
| `Id_Remitente` | `uuid` |  Nullable |
| `Rol` | `text` |  |
| `Tipo_Mensaje` | `text` |  |
| `Contenido_Cifrado` | `bytea` |  |
| `Created_At` | `timestamptz` |  |

## Table `Grupo_Encuesta`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Encuesta` | `uuid` | Primary |
| `Id_Grupo` | `uuid` |  |
| `Creado_Por` | `uuid` |  |
| `Titulo` | `text` |  Nullable |
| `Fecha_Plan` | `date` |  Nullable |
| `Hora_Plan` | `time` |  Nullable |
| `Estado` | `text` |  |
| `Id_Plan` | `uuid` |  Nullable |
| `Creada_En` | `timestamptz` |  |
| `Ronda` | `int4` |  |
| `Es_Desempate` | `bool` |  |

## Table `Grupo_Encuesta_Respuesta`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Encuesta` | `uuid` | Primary |
| `Id_Usuario` | `uuid` | Primary |
| `Nivel_Precio_Max` | `int2` |  Nullable |
| `Apto_Menores` | `bool` |  |
| `Opcion_Celiacos` | `bool` |  |
| `Opcion_Vegana` | `bool` |  |
| `Tipos` | `_text` |  |
| `Respondida_En` | `timestamptz` |  |

## Table `Grupo_Encuesta_Disponibilidad`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Disponibilidad` | `uuid` | Primary |
| `Id_Encuesta` | `uuid` |  |
| `Id_Usuario` | `uuid` |  |
| `Fecha` | `date` |  |
| `Desde` | `time` |  |
| `Hasta` | `time` |  |

## Table `Grupo_Encuesta_Opcion`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Opcion` | `uuid` | Primary |
| `Id_Encuesta` | `uuid` |  |
| `Ronda` | `int4` |  |
| `Orden` | `int4` |  |
| `Nombre` | `text` |  |
| `Precio_Min` | `numeric` |  Nullable |
| `Precio_Max` | `numeric` |  Nullable |
| `Lugares` | `jsonb` |  |

## Table `Grupo_Encuesta_Voto`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Encuesta` | `uuid` | Primary |
| `Id_Usuario` | `uuid` | Primary |
| `Ronda` | `int4` | Primary |
| `Id_Opcion` | `uuid` |  Nullable |

## Table `Publicacion`

Un plan que su autor comparte en Social (`/social`). Se puede publicar una idea
propia o un plan al que el usuario fue y ya pasó. Al borrar el plan o el usuario
se borra la publicación (y con ella fotos, likes y comentarios). Borrar una
publicación desde la app la marca `Eliminada` (no se borra la fila) y borra sus fotos.
Creada con `migraciones/social.sql`.

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Publicacion` | `uuid` | Primary, Default `gen_random_uuid()` |
| `Id_Autor` | `uuid` | Not Null, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`) |
| `Id_Plan` | `uuid` | Not Null, Foreign Key → `Plan.id_Plan` (`ON DELETE CASCADE`) |
| `Texto` | `text` | Nullable. Check: máximo 500 caracteres |
| `Visibilidad` | `text` | Not Null, Default `'amigos'`. Check: `'amigos'` (autor y sus amigos) o `'publico'` (todos) |
| `Creada_En` | `timestamptz` | Not Null, Default `now()` |
| `Eliminada` | `boolean` | Not Null, Default `false` |
| `Aspecto` | `text` | Not Null, Default `'cuadrada'`. Check: `'cuadrada'` o `'vertical'` (4:5). Formato en que se muestran sus fotos |

Índices: `Publicacion_feed_idx` (`Creada_En` desc, solo no eliminadas), `Publicacion_autor_idx`,
`Publicacion_plan_idx`, y `Publicacion_una_por_plan_idx` (UNIQUE `Id_Autor` + `Id_Plan`, solo no
eliminadas: un plan no se publica dos veces).

## Table `Publicacion_Foto`

Hasta 2 fotos por publicación. Son JPEG ya achicados en el navegador (~1080 px) y se
guardan en la propia base.

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Foto` | `uuid` | Primary, Default `gen_random_uuid()` |
| `Id_Publicacion` | `uuid` | Not Null, Foreign Key → `Publicacion.Id_Publicacion` (`ON DELETE CASCADE`) |
| `Orden` | `smallint` | Not Null. Check: 0 o 1. UNIQUE junto con `Id_Publicacion` |
| `Datos` | `bytea` | Not Null. Check: máximo 400 KB (409600 bytes) |

## Table `Publicacion_Like`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Publicacion` | `uuid` | Primary, Foreign Key → `Publicacion.Id_Publicacion` (`ON DELETE CASCADE`) |
| `Id_Usuario` | `uuid` | Primary, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`) |
| `Fecha` | `timestamptz` | Not Null, Default `now()` |

## Table `Publicacion_Comentario`

Comentarios planos (sin hilos). Los puede borrar quien comentó o el autor de la publicación
(se marca `Eliminado`).

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Comentario` | `uuid` | Primary, Default `gen_random_uuid()` |
| `Id_Publicacion` | `uuid` | Not Null, Foreign Key → `Publicacion.Id_Publicacion` (`ON DELETE CASCADE`) |
| `Id_Usuario` | `uuid` | Not Null, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`) |
| `Contenido` | `text` | Not Null. Check: entre 1 y 300 caracteres |
| `Creado_En` | `timestamptz` | Not Null, Default `now()` |
| `Eliminado` | `boolean` | Not Null, Default `false` |

## Table `Publicacion_Reporte`

Denuncias de publicaciones o comentarios. No hay pantalla de moderación: el equipo las
revisa directo en la base (`SELECT * FROM "Publicacion_Reporte" WHERE NOT "Revisado" ORDER BY "Creado_En";`).

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Reporte` | `uuid` | Primary, Default `gen_random_uuid()` |
| `Tipo` | `text` | Not Null. Check: `'publicacion'` o `'comentario'` |
| `Id_Objetivo` | `uuid` | Not Null. Id de la publicación o del comentario (sin Foreign Key, depende de `Tipo`) |
| `Id_Reportante` | `uuid` | Not Null, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`) |
| `Motivo` | `text` | Nullable. Check: máximo 300 caracteres |
| `Creado_En` | `timestamptz` | Not Null, Default `now()` |
| `Revisado` | `boolean` | Not Null, Default `false` |

UNIQUE (`Id_Reportante`, `Tipo`, `Id_Objetivo`): cada persona reporta una vez lo mismo.

## Table `Publicacion_Notificacion`

Avisos para el autor de una publicación cuando alguien le da me gusta o le comenta.
Se ven en Inbox > Publicaciones (los me gusta de una misma publicación se muestran
juntos). Se borran al sacar el me gusta, borrar el comentario o eliminar la publicación.
Creada con `migraciones/social_inbox.sql`.

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Notificacion` | `uuid` | Primary, Default `gen_random_uuid()` |
| `Id_Usuario` | `uuid` | Not Null, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`). Quién recibe el aviso |
| `Id_Actor` | `uuid` | Not Null, Foreign Key → `Usuarios.Id_Usuario` (`ON DELETE CASCADE`). Quién dio me gusta o comentó |
| `Tipo` | `text` | Not Null. Check: `'like'` o `'comentario'` |
| `Id_Publicacion` | `uuid` | Not Null, Foreign Key → `Publicacion.Id_Publicacion` (`ON DELETE CASCADE`) |
| `Id_Comentario` | `uuid` | Nullable, Foreign Key → `Publicacion_Comentario.Id_Comentario` (`ON DELETE CASCADE`). Solo en los avisos de comentario |
| `Creada_En` | `timestamptz` | Not Null, Default `now()` |
| `Leida` | `boolean` | Not Null, Default `false` |

Índices: `Publicacion_Notificacion_usuario_idx` (`Id_Usuario`, `Creada_En` desc),
`Publicacion_Notificacion_no_leidas_idx` (`Id_Usuario`, solo no leídas) y
`Publicacion_Notificacion_like_uq` (UNIQUE `Id_Usuario` + `Id_Publicacion` + `Id_Actor`, solo
`Tipo = 'like'`: un aviso de me gusta por persona y publicación).

## RLS Policies

### `Usuario-Grupo`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_se_une_a_grupo` | INSERT | public | PERMISSIVE | — | `(auth.uid() = "Id_Usuario")` |
| `usuario_ve_su_membresia` | SELECT | public | PERMISSIVE | `(auth.uid() = "Id_Usuario")` | — |

### `Plan`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_crea_plan` | INSERT | public | PERMISSIVE | — | `true` |
| `usuario_ve_planes_de_sus_grupos` | SELECT | public | PERMISSIVE | `(EXISTS ( SELECT 1    FROM "Usuario-Grupo" ug   WHERE ((ug."Id_Grupo" = "Plan"."Grupo_id") AND (ug."Id_Usuario" = auth.uid()))))` | — |

### `Grupos`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_crea_grupo` | INSERT | public | PERMISSIVE | — | `(auth.uid() = "Creado_Por")` |
| `usuario_ve_sus_grupos` | SELECT | public | PERMISSIVE | `(EXISTS ( SELECT 1    FROM "Usuario-Grupo" ug   WHERE ((ug."Id_Grupo" = "Grupos"."Id_Grupo") AND (ug."Id_Usuario" = auth.uid()))))` | — |

### `horario_lugar`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `lectura_publica_horario` | SELECT | public | PERMISSIVE | `true` | — |

### `Lugar`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `lectura_publica_lugar` | SELECT | public | PERMISSIVE | `true` | — |

### `Usuario-Plan`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_inserta_su_asistencia` | INSERT | public | PERMISSIVE | — | `(auth.uid() = "Usuario_id")` |
| `usuario_ve_su_asistencia` | SELECT | public | PERMISSIVE | `(auth.uid() = "Usuario_id")` | — |

### `Usuarios`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_edita_su_perfil` | UPDATE | public | PERMISSIVE | `(auth.uid() = "Id_Usuario")` | — |
| `usuario_ve_su_perfil` | SELECT | public | PERMISSIVE | `(auth.uid() = "Id_Usuario")` | — |

### Tablas de Social (`Publicacion`, `Publicacion_Foto`, `Publicacion_Like`, `Publicacion_Comentario`, `Publicacion_Reporte`, `Publicacion_Notificacion`)

Tienen RLS activado y **sin políticas**: la API pública de Supabase (clave `anon`) no puede
leerlas ni escribirlas. La app entra con el usuario de la base (`postgres`), que no pasa por
RLS, y aplica las reglas de visibilidad en `services/social_service.py`.
