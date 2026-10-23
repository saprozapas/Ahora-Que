-- =============================================================================
-- ORIGEN DEL PRECIO DE CADA LUGAR
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez.
-- Es idempotente (IF NOT EXISTS). No toca ninguna fila existente.
--
-- "Lugar"."Precio_Origen" dice de dónde salió la categoría de "Nivel_Precio":
--   marca    cadena o lugar conocido (McDonald's, Grido, Nippon...)
--   cocina   etiqueta "cuisine" de OpenStreetMap (sushi, steak_house...)
--   nombre   palabras del nombre (parrilla, pizzería, cervecería...)
--   tipo     lo normal para ese tipo de lugar (la estimación menos confiable)
--   manual   la puso una persona: scripts/estimar_precios.py nunca la pisa
--   NULL     el precio no se estimó (por ejemplo, los gratis cargados con la importación)
-- Sirve para saber qué precios son estimaciones, filtrarlos y corregirlos.
-- =============================================================================

BEGIN;

ALTER TABLE public."Lugar"
    ADD COLUMN IF NOT EXISTS "Precio_Origen" text
    CHECK ("Precio_Origen" IN ('marca', 'cocina', 'nombre', 'tipo', 'manual'));

COMMIT;
