-- =============================================================================
-- CATEGORÍAS DE PRECIO: de 5 a 6 (0 a 5)
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez.
-- Es repetible: borra la regla vieja si está y vuelve a crear la nueva.
--
-- Las categorías de la app son:
--   0  Gratis
--   1  $      de 100 a 300 pesos
--   2  $$     de 300 a 600 pesos
--   3  $$$    de 600 a 1000 pesos
--   4  $$$$   de 1000 a 2000 pesos
--   5  $$$$$  más de 2000 pesos
--
-- La base solo aceptaba hasta 4. Esto amplía las dos reglas que lo limitaban:
--   "Lugar"."Nivel_Precio"                       0 a 5 (antes 0 a 4)
--   "Grupo_Encuesta_Respuesta"."Nivel_Precio_Max" 1 a 5 (antes 1 a 4)
-- Los datos existentes (0 y NULL) siguen siendo válidos: no cambia ninguna fila.
-- Los montos en pesos de cada categoría viven en services/precio_lugar.py.
-- =============================================================================

BEGIN;

ALTER TABLE public."Lugar"
    DROP CONSTRAINT IF EXISTS "Lugar_Nivel_Precio_check";
ALTER TABLE public."Lugar"
    ADD CONSTRAINT "Lugar_Nivel_Precio_check"
    CHECK ("Nivel_Precio" >= 0 AND "Nivel_Precio" <= 5);

ALTER TABLE public."Grupo_Encuesta_Respuesta"
    DROP CONSTRAINT IF EXISTS "Grupo_Encuesta_Respuesta_Nivel_Precio_Max_check";
ALTER TABLE public."Grupo_Encuesta_Respuesta"
    ADD CONSTRAINT "Grupo_Encuesta_Respuesta_Nivel_Precio_Max_check"
    CHECK ("Nivel_Precio_Max" >= 1 AND "Nivel_Precio_Max" <= 5);

COMMIT;
