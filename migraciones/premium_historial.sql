-- =============================================================================
-- HISTORIAL DE PREMIUM (correr una sola vez; es idempotente)
--
-- Una fila por cada alta o baja de Premium. Sirve para poder demostrar:
--   * cuándo aceptó la persona las condiciones de Premium y cuál era su versión
--     (services/legal_info.py: VERSION_CONDICIONES_PREMIUM),
--   * cuándo canceló.
-- Al eliminar la cuenta se borra con ella (ON DELETE CASCADE), igual que el resto.
--
-- RLS activado y SIN políticas (igual que el resto): la app entra con el usuario
-- de la base y aplica las reglas en services/suscripcion_service.py.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public."Premium_Historial" (
    "Id_Evento"           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "Id_Usuario"          uuid NOT NULL REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Accion"              text NOT NULL CHECK ("Accion" IN ('alta', 'baja')),
    "Ciclo"               text CHECK ("Ciclo" IN ('mensual', 'anual')),
    "Version_Condiciones" text,
    "Creado_En"           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS "Premium_Historial_usuario_idx"
    ON public."Premium_Historial" ("Id_Usuario", "Creado_En" DESC);

ALTER TABLE public."Premium_Historial" ENABLE ROW LEVEL SECURITY;

COMMIT;
