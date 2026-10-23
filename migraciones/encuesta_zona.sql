-- =============================================================================
-- ENCUESTAS DE GRUPO: ZONA Y DISTANCIA
--
-- Cada integrante puede indicar, además del precio, las restricciones, los tipos
-- de lugar y sus horarios:
--   "Barrio"           barrio desde donde sale (nombre tal cual está en "Lugar"."Barrio").
--   "Distancia_Max_Km" hasta cuántos km de ese barrio está dispuesta a ir.
-- Las dos son opcionales (NULL = sin preferencia). No se guarda ninguna ubicación
-- exacta de la persona: solo el nombre del barrio.
--
-- Es idempotente (se puede correr más de una vez) y no cambia las filas que ya
-- existen: las encuestas viejas quedan con las dos columnas en NULL.
-- =============================================================================

BEGIN;

ALTER TABLE public."Grupo_Encuesta_Respuesta"
    ADD COLUMN IF NOT EXISTS "Barrio"           text,
    ADD COLUMN IF NOT EXISTS "Distancia_Max_Km" smallint;

COMMIT;
