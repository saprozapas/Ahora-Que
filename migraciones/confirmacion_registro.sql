-- Registros pendientes: el usuario no se crea en "Usuarios" hasta confirmar.
CREATE TABLE IF NOT EXISTS public."Confirmaciones_Registro" (
    "Id_Usuario" uuid PRIMARY KEY,
    "Codigo_Hash" text NOT NULL UNIQUE,
    "Nombre" text NOT NULL,
    "Mail" text NOT NULL,
    "Fecha_Nac" date NOT NULL,
    "Password_Hash" text NOT NULL,
    "Username" text NOT NULL,
    "Descripcion" text,
    "Creado_En" timestamptz NOT NULL DEFAULT NOW(),
    "Expira_En" timestamptz NOT NULL,
    CONSTRAINT "Confirmaciones_Registro_Mail_key" UNIQUE ("Mail"),
    CONSTRAINT "Confirmaciones_Registro_Username_key" UNIQUE ("Username")
);
