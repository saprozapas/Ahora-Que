-- =============================================================================
-- ACEPTACIÓN LEGAL DEL REGISTRO (correr una sola vez; es idempotente y solo AGREGA)
--
-- Deja constancia de qué aceptó cada persona al crear su cuenta:
--   * la versión de los términos y la de la política de privacidad (services/legal_info.py),
--   * la fecha y hora,
--   * si declaró que su madre, padre o tutor lo autoriza (obligatorio entre 13 y 17 años).
-- (Ley 18.331, art. 9: el consentimiento debe ser documentado.)
--
-- Mientras la cuenta está pendiente de confirmar, la constancia viaja en "Confirmaciones_Registro";
-- al confirmar el correo se copia a "Aceptaciones_Legales", que se borra junto con la cuenta
-- (ON DELETE CASCADE), igual que el resto de los datos.
-- RLS activada y SIN políticas, igual que el resto: la app entra con el usuario de la base.
-- =============================================================================

BEGIN;

ALTER TABLE public."Confirmaciones_Registro"
    ADD COLUMN IF NOT EXISTS "Version_Terminos"   text,
    ADD COLUMN IF NOT EXISTS "Version_Privacidad" text,
    ADD COLUMN IF NOT EXISTS "Aceptado_En"        timestamptz,
    ADD COLUMN IF NOT EXISTS "Tutor_Declarado"    boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS public."Aceptaciones_Legales" (
    "Id_Aceptacion"      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "Id_Usuario"         uuid NOT NULL REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Version_Terminos"   text NOT NULL,
    "Version_Privacidad" text NOT NULL,
    "Aceptado_En"        timestamptz NOT NULL,
    "Tutor_Declarado"    boolean NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS "Aceptaciones_Legales_usuario_idx"
    ON public."Aceptaciones_Legales" ("Id_Usuario");

ALTER TABLE public."Aceptaciones_Legales" ENABLE ROW LEVEL SECURITY;

COMMIT;
