-- =============================================================================
-- INICIO: SUGERENCIAS SEMANALES, UBICACIONES DEL PLAN Y MENCIONES
--
-- Solo agrega (no cambia ni borra nada de lo que ya existe). Es idempotente:
-- se puede correr más de una vez.
--
--   "Sugerencia_Semanal"   los 3 planes que el asistente le sugiere a cada usuario por semana
--                          ("Semana" = el lunes de esa semana). Al cambiar la semana se generan otros.
--   "Plan_Ubicacion"       la ÚLTIMA ubicación que cada asistente eligió compartir en un plan confirmado
--                          (opcional, una fila por persona y plan, nunca un historial). Se borra al dejar
--                          de compartir y cuando el plan deja de estar confirmado.
--   "Usuario-Grupo"."Chat_Visto_En"   hasta cuándo leyó cada integrante el chat de su grupo: las
--                          menciones (@usuario / @all) posteriores son las que avisa el Inicio. Las filas
--                          que ya existen arrancan en "ahora", así no llega un aluvión de avisos viejos.
--                          Misma hora que "Mensajes"."Fecha_Envio" (hora de Montevideo, sin zona).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public."Sugerencia_Semanal" (
    "Id_Sugerencia" uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Usuario"    uuid        NOT NULL REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Semana"        date        NOT NULL,
    "Orden"         smallint    NOT NULL,
    "Nombre"        text        NOT NULL,
    "Descripcion"   text,
    "Lugares"       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    "Creada_En"     timestamptz NOT NULL DEFAULT now(),
    UNIQUE ("Id_Usuario", "Semana", "Orden")
);

CREATE TABLE IF NOT EXISTS public."Plan_Ubicacion" (
    "Id_Plan"        uuid             NOT NULL REFERENCES public."Plan" ("id_Plan") ON DELETE CASCADE,
    "Id_Usuario"     uuid             NOT NULL REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Lat"            double precision NOT NULL,
    "Lon"            double precision NOT NULL,
    "Actualizada_En" timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY ("Id_Plan", "Id_Usuario")
);

ALTER TABLE public."Usuario-Grupo"
    ADD COLUMN IF NOT EXISTS "Chat_Visto_En" timestamp without time zone
    NOT NULL DEFAULT (now() AT TIME ZONE 'America/Montevideo');

COMMIT;
