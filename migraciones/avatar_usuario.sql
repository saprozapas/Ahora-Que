-- =============================================================================
-- FOTO DE PERFIL
--
-- Solo agrega una tabla (no cambia nada de lo existente). Es idempotente.
--
--   "Usuario_Avatar"   una fila por usuario con foto elegida:
--     "Tipo"    'preset' (uno de los 5 avatares genéricos, "Preset" 1-5) o 'foto' (una imagen subida: JPEG
--               cuadrada y chica, en "Datos", igual que las fotos de las publicaciones).
--   Sin fila, el usuario no tiene foto y se muestra su inicial. Se borra sola con la cuenta.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public."Usuario_Avatar" (
    "Id_Usuario"     uuid        PRIMARY KEY REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Tipo"           text        NOT NULL CHECK ("Tipo" IN ('preset', 'foto')),
    "Preset"         smallint    CHECK ("Preset" BETWEEN 1 AND 5),
    "Datos"          bytea,
    "Actualizada_En" timestamptz NOT NULL DEFAULT now()
);

COMMIT;
