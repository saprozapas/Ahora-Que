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
| `Nivel_Precio` | `int4` |  Nullable |
| `Imagen_Url` | `text` |  Nullable |

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

## Table `Usuario-Grupo`

Conecto Usuarios con Grupos

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `Id_Usuario` | `uuid` | Primary |
| `Id_Grupo` | `uuid` | Primary |

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

### `horario_lugar`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `lectura_publica_horario` | SELECT | public | PERMISSIVE | `true` | — |

### `Grupos`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_crea_grupo` | INSERT | public | PERMISSIVE | — | `(auth.uid() = "Creado_Por")` |
| `usuario_ve_sus_grupos` | SELECT | public | PERMISSIVE | `(EXISTS ( SELECT 1    FROM "Usuario-Grupo" ug   WHERE ((ug."Id_Grupo" = "Grupos"."Id_Grupo") AND (ug."Id_Usuario" = auth.uid()))))` | — |

### `Usuario-Plan`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_inserta_su_asistencia` | INSERT | public | PERMISSIVE | — | `(auth.uid() = "Usuario_id")` |
| `usuario_ve_su_asistencia` | SELECT | public | PERMISSIVE | `(auth.uid() = "Usuario_id")` | — |

### `Lugar`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `lectura_publica_lugar` | SELECT | public | PERMISSIVE | `true` | — |

### `Usuarios`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `usuario_edita_su_perfil` | UPDATE | public | PERMISSIVE | `(auth.uid() = "Id_Usuario")` | — |
| `usuario_ve_su_perfil` | SELECT | public | PERMISSIVE | `(auth.uid() = "Id_Usuario")` | — |

