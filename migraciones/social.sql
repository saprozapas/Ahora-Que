-- =============================================================================
-- SOCIAL: publicaciones, likes, comentarios y reportes
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez.
-- Es idempotente (CREATE ... IF NOT EXISTS): si se corre de nuevo, no pasa
-- nada. No toca ninguna tabla existente.
--
-- Qué crea:
--   "Publicacion"             un plan compartido por su autor, con un texto
--                             y quién lo puede ver ('amigos' o 'publico').
--   "Publicacion_Like"        un "me gusta" por usuario y publicación.
--   "Publicacion_Comentario"  comentarios planos (sin hilos).
--   "Publicacion_Reporte"     denuncias de publicaciones o comentarios, para
--                             que el equipo las revise directo en la base.
--
-- Si se borra el plan, se borra su publicación y con ella los likes y
-- comentarios (ON DELETE CASCADE). Si se borra un usuario, lo mismo con lo
-- suyo.
--
-- Las tablas quedan con RLS activado y SIN políticas: la API pública de
-- Supabase (clave anon) no puede leerlas ni escribirlas. La app entra con
-- el usuario de la base, que no pasa por RLS.
-- =============================================================================

BEGIN;


-- -----------------------------------------------------------------------------
-- Publicacion
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public."Publicacion" (
    "Id_Publicacion" uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Autor"       uuid        NOT NULL
                     REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Id_Plan"        uuid        NOT NULL
                     REFERENCES public."Plan" ("id_Plan") ON DELETE CASCADE,
    "Texto"          text        CHECK (char_length("Texto") <= 500),
    "Visibilidad"    text        NOT NULL DEFAULT 'amigos'
                     CHECK ("Visibilidad" IN ('amigos', 'publico')),
    "Creada_En"      timestamptz NOT NULL DEFAULT now(),
    "Eliminada"      boolean     NOT NULL DEFAULT false
);

-- El feed: lo más nuevo primero.
CREATE INDEX IF NOT EXISTS "Publicacion_feed_idx"
    ON public."Publicacion" ("Creada_En" DESC)
    WHERE NOT "Eliminada";

-- "Mis publicaciones" y el perfil de cada persona.
CREATE INDEX IF NOT EXISTS "Publicacion_autor_idx"
    ON public."Publicacion" ("Id_Autor", "Creada_En" DESC)
    WHERE NOT "Eliminada";

-- Un mismo plan no se publica dos veces (si se borró la publicación, se
-- puede volver a publicar).
CREATE UNIQUE INDEX IF NOT EXISTS "Publicacion_una_por_plan_idx"
    ON public."Publicacion" ("Id_Autor", "Id_Plan")
    WHERE NOT "Eliminada";

-- Para que borrar un plan no recorra toda la tabla.
CREATE INDEX IF NOT EXISTS "Publicacion_plan_idx"
    ON public."Publicacion" ("Id_Plan");


-- -----------------------------------------------------------------------------
-- Publicacion_Like
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public."Publicacion_Like" (
    "Id_Publicacion" uuid        NOT NULL
                     REFERENCES public."Publicacion" ("Id_Publicacion") ON DELETE CASCADE,
    "Id_Usuario"     uuid        NOT NULL
                     REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Fecha"          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("Id_Publicacion", "Id_Usuario")
);

CREATE INDEX IF NOT EXISTS "Publicacion_Like_usuario_idx"
    ON public."Publicacion_Like" ("Id_Usuario");


-- -----------------------------------------------------------------------------
-- Publicacion_Comentario
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public."Publicacion_Comentario" (
    "Id_Comentario"  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Publicacion" uuid        NOT NULL
                     REFERENCES public."Publicacion" ("Id_Publicacion") ON DELETE CASCADE,
    "Id_Usuario"     uuid        NOT NULL
                     REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Contenido"      text        NOT NULL
                     CHECK (char_length("Contenido") BETWEEN 1 AND 300),
    "Creado_En"      timestamptz NOT NULL DEFAULT now(),
    "Eliminado"      boolean     NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS "Publicacion_Comentario_publicacion_idx"
    ON public."Publicacion_Comentario" ("Id_Publicacion", "Creado_En")
    WHERE NOT "Eliminado";

CREATE INDEX IF NOT EXISTS "Publicacion_Comentario_usuario_idx"
    ON public."Publicacion_Comentario" ("Id_Usuario", "Creado_En" DESC);


-- -----------------------------------------------------------------------------
-- Publicacion_Reporte
--
-- Para revisarlos:
--   SELECT * FROM "Publicacion_Reporte" WHERE NOT "Revisado" ORDER BY "Creado_En";
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public."Publicacion_Reporte" (
    "Id_Reporte"     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Tipo"           text        NOT NULL CHECK ("Tipo" IN ('publicacion', 'comentario')),
    "Id_Objetivo"    uuid        NOT NULL,
    "Id_Reportante"  uuid        NOT NULL
                     REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Motivo"         text        CHECK (char_length("Motivo") <= 300),
    "Creado_En"      timestamptz NOT NULL DEFAULT now(),
    "Revisado"       boolean     NOT NULL DEFAULT false,
    UNIQUE ("Id_Reportante", "Tipo", "Id_Objetivo")
);


-- -----------------------------------------------------------------------------
-- RLS: activado y sin políticas (solo entra la app, no la API pública).
-- -----------------------------------------------------------------------------

ALTER TABLE public."Publicacion"             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Publicacion_Like"        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Publicacion_Comentario"  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Publicacion_Reporte"     ENABLE ROW LEVEL SECURITY;

COMMIT;
