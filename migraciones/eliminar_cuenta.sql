-- Eliminar cuenta: al borrarse el creador, sus grupos/encuestas quedan sin creador (NULL).
-- Idempotente: si ya admiten NULL, no pasa nada.
BEGIN;
ALTER TABLE public."Grupos"         ALTER COLUMN "Creado_Por" DROP NOT NULL;
ALTER TABLE public."Grupo_Encuesta" ALTER COLUMN "Creado_Por" DROP NOT NULL;
COMMIT;
