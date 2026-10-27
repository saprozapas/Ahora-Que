-- Preferencias de los correos que corresponden a pendientes del dashboard.
-- Ejecutar una vez en Supabase / PostgreSQL.
CREATE TABLE IF NOT EXISTS public."Preferencias_Notificacion" (
    "Id_Usuario" uuid PRIMARY KEY REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Solicitudes_Amistad" boolean NOT NULL DEFAULT true,
    "Invitaciones_Grupo" boolean NOT NULL DEFAULT true,
    "Votos_Grupo" boolean NOT NULL DEFAULT true,
    "Puntuar_Plan" boolean NOT NULL DEFAULT true,
    "Menciones_Chat" boolean NOT NULL DEFAULT true
);

ALTER TABLE public."Preferencias_Notificacion"
    ADD COLUMN IF NOT EXISTS "Menciones_Chat" boolean NOT NULL DEFAULT true;

ALTER TABLE public."Preferencias_Notificacion" ENABLE ROW LEVEL SECURITY;
