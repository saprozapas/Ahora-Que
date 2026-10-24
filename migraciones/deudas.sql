-- =============================================================================
-- DEUDAS: repartos de gastos entre amigos y saldo entre cada par de personas
--
-- Cómo correrlo: Supabase -> SQL Editor -> pegar todo -> Run. Una sola vez.
-- Es idempotente (CREATE ... IF NOT EXISTS) y no toca ninguna tabla existente.
--
--   "Deuda_Reparto"               una salida a dividir (quién la creó, de qué grupo
--                                 si vino de uno, y si ya se calculó).
--   "Deuda_Reparto_Participante"  cuánto gastó y cuánto pagó cada uno. NULL = todavía
--                                 no lo cargó. Cuando no queda ningún NULL se calcula.
--   "Deuda"                       UNA fila por par de personas (se netea sola).
--                                 Saldo > 0: Id_Usuario1 le debe a Id_Usuario2.
--                                 Saldo < 0: Id_Usuario2 le debe a Id_Usuario1.
--                                 Se borra cuando el acreedor marca "fue pagado".
--
-- RLS activado y SIN políticas (igual que Social): la app entra con el usuario de
-- la base y aplica las reglas en services/deuda_service.py.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public."Deuda_Reparto" (
    "Id_Reparto" uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    "Id_Creador" uuid        NOT NULL
                 REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Id_Grupo"   uuid
                 REFERENCES public."Grupos" ("Id_Grupo") ON DELETE SET NULL,
    "Descripcion" text       NOT NULL CHECK (char_length("Descripcion") BETWEEN 1 AND 100),
    "Calculado"  boolean     NOT NULL DEFAULT false,
    "Creado_En"  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public."Deuda_Reparto_Participante" (
    "Id_Reparto" uuid NOT NULL
                 REFERENCES public."Deuda_Reparto" ("Id_Reparto") ON DELETE CASCADE,
    "Id_Usuario" uuid NOT NULL
                 REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Gasto"      numeric(12,2) CHECK ("Gasto" >= 0),
    "Pago"       numeric(12,2) CHECK ("Pago" >= 0),
    PRIMARY KEY ("Id_Reparto", "Id_Usuario")
);

CREATE INDEX IF NOT EXISTS "Deuda_Reparto_Participante_usuario_idx"
    ON public."Deuda_Reparto_Participante" ("Id_Usuario");

CREATE TABLE IF NOT EXISTS public."Deuda" (
    "Id_Usuario1" uuid NOT NULL
                  REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Id_Usuario2" uuid NOT NULL
                  REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Saldo"       numeric(12,2) NOT NULL CHECK ("Saldo" <> 0),
    PRIMARY KEY ("Id_Usuario1", "Id_Usuario2"),
    CHECK ("Id_Usuario1" < "Id_Usuario2")
);

CREATE INDEX IF NOT EXISTS "Deuda_usuario2_idx" ON public."Deuda" ("Id_Usuario2");

ALTER TABLE public."Deuda_Reparto"              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Deuda_Reparto_Participante" ENABLE ROW LEVEL SECURITY;
ALTER TABLE public."Deuda"                      ENABLE ROW LEVEL SECURITY;

COMMIT;
