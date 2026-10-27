-- Suscripciones por navegador/dispositivo para Web Push.
-- Ejecutar una vez en Supabase / PostgreSQL.
BEGIN;

CREATE TABLE IF NOT EXISTS public."Notificacion_Push_Suscripcion" (
    "Id_Suscripcion" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Usuario" uuid NOT NULL REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Endpoint" text NOT NULL UNIQUE,
    "P256dh" text NOT NULL,
    "Auth" text NOT NULL,
    "Activa" boolean NOT NULL DEFAULT true,
    "Creada_En" timestamptz NOT NULL DEFAULT now(),
    "Actualizada_En" timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS "Notificacion_Push_Suscripcion_usuario_idx"
    ON public."Notificacion_Push_Suscripcion" ("Id_Usuario")
    WHERE "Activa";

ALTER TABLE public."Notificacion_Push_Suscripcion" ENABLE ROW LEVEL SECURITY;

COMMIT;
