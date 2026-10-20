-- =============================================================================
-- LUGARES DE OPENSTREETMAP: columnas nuevas de "Lugar"
--
-- Esta migración YA está aplicada en la base compartida (se guarda acá para
-- que quede registro y se pueda repetir en otra base). Es idempotente: si se
-- corre de nuevo no cambia nada.
--
-- La usa scripts/importar_osm.py:
--   "Osm_Id"     id del lugar en OpenStreetMap ('node/123', 'way/456',
--                'relation/789'). UNIQUE: permite el upsert de la importación.
--   "Fuente"     de dónde salió el lugar: 'manual' (default) u 'osm'.
--   "Verificado" true = alguien lo corrigió a mano; la importación no lo pisa.
--   "Barrio"     nombre del barrio, tal cual lo da OpenStreetMap (NULL = se
--                desconoce).
--
-- Nota: reconstruida a partir del estado real de la base (columnas, defaults
-- e índice "lugar_osm_id_uq"), no es el archivo original que se corrió.
-- =============================================================================

BEGIN;

ALTER TABLE public."Lugar"
    ADD COLUMN IF NOT EXISTS "Osm_Id"     text,
    ADD COLUMN IF NOT EXISTS "Fuente"     text    NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS "Verificado" boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS "Barrio"     text;

-- Un único índice UNIQUE sobre "Osm_Id" (varios NULL están permitidos: los
-- lugares cargados a mano no tienen Osm_Id).
CREATE UNIQUE INDEX IF NOT EXISTS lugar_osm_id_uq
    ON public."Lugar" ("Osm_Id");

COMMIT;
