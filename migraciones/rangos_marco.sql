-- El rango de un grupo (Marco_Semanas) se guarda como las semanas del hito. La restricción vieja solo dejaba
-- 3, 10, 30, 70 y 100, así que elegir Tierra (20) o Marte (40) fallaba y la tarjeta seguía con el rango más alto.
-- Ahora acepta los mismos hitos que Titulo_Semanas y Grupo_Insignia. No toca ninguna fila.
BEGIN;
ALTER TABLE public."Grupo_Apariencia" DROP CONSTRAINT IF EXISTS "Grupo_Apariencia_Marco_Semanas_check";
ALTER TABLE public."Grupo_Apariencia" ADD CONSTRAINT "Grupo_Apariencia_Marco_Semanas_check"
  CHECK ("Marco_Semanas" IS NULL OR "Marco_Semanas" = ANY (ARRAY[3, 5, 10, 20, 30, 40, 50, 70, 90, 100]));
COMMIT;
