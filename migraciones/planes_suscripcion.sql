-- =============================================================================
-- PLANES GRATIS / PREMIUM (correr una sola vez; es idempotente)
--
--   1. Usuarios."Premium": quien lo tiene en true es del plan pago (estrella en el
--      nombre y sin límite de IA). Por ahora no hay pagos: se activa a mano con
--          UPDATE public."Usuarios" SET "Premium" = true WHERE "Username" = '...';
--   2. Uso_IA_Plan: una fila por cada plan que alguien guarda o postula armado con
--      la IA. El plan gratis tiene 1 por semana (la semana arranca el lunes).
--
-- RLS activado y SIN políticas (igual que el resto): la app entra con el usuario
-- de la base y aplica las reglas en services/suscripcion_service.py.
-- =============================================================================

BEGIN;

ALTER TABLE public."Usuarios" ADD COLUMN IF NOT EXISTS "Premium" boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS public."Uso_IA_Plan" (
    "Id_Uso"     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Usuario" uuid        NOT NULL
                 REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Creado_En"  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS "Uso_IA_Plan_usuario_fecha"
    ON public."Uso_IA_Plan" ("Id_Usuario", "Creado_En");

ALTER TABLE public."Uso_IA_Plan" ENABLE ROW LEVEL SECURITY;

COMMIT;
