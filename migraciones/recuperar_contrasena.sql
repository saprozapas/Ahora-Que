-- "Olvidé mi contraseña": un código vigente por usuario (se guarda su hash, nunca el código).
CREATE TABLE IF NOT EXISTS public."Recuperacion_Contrasena" (
    "Id_Usuario" uuid PRIMARY KEY REFERENCES public."Usuarios" ("Id_Usuario") ON DELETE CASCADE,
    "Codigo_Hash" text NOT NULL UNIQUE,
    "Expira_En" timestamptz NOT NULL
);
