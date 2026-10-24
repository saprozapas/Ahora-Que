-- =============================================================================
-- DEUDAS v2 (correr DESPUÉS de deudas.sql, una sola vez; es idempotente)
--
--   1. El nombre de la salida pasa a ser opcional ("Descripcion" puede ser NULL).
--   2. Cuenta bancaria de cada usuario (se edita en el perfil): la ve solo quien
--      le debe plata, en la pantalla de Deudas, para saber a dónde transferir.
--
-- RLS activado y SIN políticas (igual que el resto): la app entra con el usuario
-- de la base y aplica las reglas en services/deuda_service.py.
-- =============================================================================

BEGIN;

ALTER TABLE public."Deuda_Reparto" ALTER COLUMN "Descripcion" DROP NOT NULL;
ALTER TABLE public."Deuda_Reparto" DROP CONSTRAINT IF EXISTS "Deuda_Reparto_Descripcion_check";
ALTER TABLE public."Deuda_Reparto" DROP CONSTRAINT IF EXISTS "Deuda_Reparto_Descripcion_largo";
ALTER TABLE public."Deuda_Reparto" ADD CONSTRAINT "Deuda_Reparto_Descripcion_largo"
    CHECK ("Descripcion" IS NULL OR char_length("Descripcion") BETWEEN 1 AND 100);

CREATE TABLE IF NOT EXISTS public."Cuenta_Bancaria" (
    "Id_Usuario" uuid PRIMARY KEY
                 REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Banco"      text NOT NULL CHECK (char_length("Banco") BETWEEN 1 AND 60),
    "Nro_Cuenta" text NOT NULL CHECK (char_length("Nro_Cuenta") BETWEEN 1 AND 40)
);

ALTER TABLE public."Cuenta_Bancaria" ENABLE ROW LEVEL SECURITY;

COMMIT;
