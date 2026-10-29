-- Número de cuenta bancaria cifrado (ver services/crypto_service.py: cifrar_campo).
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez, ANTES de desplegar el código nuevo.
--
-- Qué hace: el número de cuenta cifrado es más largo que el original (nonce + etiqueta + base64), así que se
-- agranda el límite del CHECK de la columna. La app limita igual a 40 caracteres lo que escribe la persona.
-- Después de desplegar, correr una vez:  python scripts/cifrar_cuentas_existentes.py

BEGIN;

ALTER TABLE public."Cuenta_Bancaria"
    DROP CONSTRAINT IF EXISTS "Cuenta_Bancaria_Nro_Cuenta_check";

ALTER TABLE public."Cuenta_Bancaria"
    ADD CONSTRAINT "Cuenta_Bancaria_Nro_Cuenta_check"
    CHECK (char_length("Nro_Cuenta") BETWEEN 1 AND 400);

COMMIT;
