-- =============================================================================
-- SOCIAL, SEGUNDA PARTE: avisos en el Inbox y formato de la foto
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez.
-- Es idempotente (IF NOT EXISTS): si se corre de nuevo, no pasa nada. Hay que
-- correr antes migraciones/social.sql.
--
-- Qué hace:
--   "Publicacion"."Aspecto"        formato de las fotos de la publicación:
--                                  'cuadrada' (default) o 'vertical' (4:5).
--   "Publicacion_Notificacion"     un aviso para el autor cuando alguien le da
--                                  me gusta o le comenta una publicación. Se
--                                  ven en Inbox > Publicaciones.
--
-- Las tablas nuevas quedan con RLS activado y SIN políticas, igual que el resto
-- de Social: la app entra con el usuario de la base y la API pública no ve nada.
-- =============================================================================

BEGIN;

ALTER TABLE public."Publicacion"
    ADD COLUMN IF NOT EXISTS "Aspecto" text NOT NULL DEFAULT 'cuadrada'
    CHECK ("Aspecto" IN ('cuadrada', 'vertical'));


CREATE TABLE IF NOT EXISTS public."Publicacion_Notificacion" (
    "Id_Notificacion" uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Quién recibe el aviso (el autor de la publicación).
    "Id_Usuario"      uuid        NOT NULL
                      REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    -- Quién dio me gusta o comentó.
    "Id_Actor"        uuid        NOT NULL
                      REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Tipo"            text        NOT NULL CHECK ("Tipo" IN ('like', 'comentario')),
    "Id_Publicacion"  uuid        NOT NULL
                      REFERENCES public."Publicacion" ("Id_Publicacion") ON DELETE CASCADE,
    -- Solo para Tipo = 'comentario'.
    "Id_Comentario"   uuid
                      REFERENCES public."Publicacion_Comentario" ("Id_Comentario") ON DELETE CASCADE,
    "Creada_En"       timestamptz NOT NULL DEFAULT now(),
    "Leida"           boolean     NOT NULL DEFAULT false
);

-- La lista del Inbox: lo más nuevo primero.
CREATE INDEX IF NOT EXISTS "Publicacion_Notificacion_usuario_idx"
    ON public."Publicacion_Notificacion" ("Id_Usuario", "Creada_En" DESC);

-- El contador de la barra lateral solo mira lo no leído.
CREATE INDEX IF NOT EXISTS "Publicacion_Notificacion_no_leidas_idx"
    ON public."Publicacion_Notificacion" ("Id_Usuario")
    WHERE NOT "Leida";

-- Un solo aviso de me gusta por persona y publicación (dar y sacar el me gusta
-- varias veces no llena el Inbox).
CREATE UNIQUE INDEX IF NOT EXISTS "Publicacion_Notificacion_like_uq"
    ON public."Publicacion_Notificacion" ("Id_Usuario", "Id_Publicacion", "Id_Actor")
    WHERE "Tipo" = 'like';

ALTER TABLE public."Publicacion_Notificacion" ENABLE ROW LEVEL SECURITY;

COMMIT;
