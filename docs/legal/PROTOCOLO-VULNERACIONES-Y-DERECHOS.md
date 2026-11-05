# Protocolos de Ahora Qué: vulneraciones de seguridad y derechos de las personas

Documento interno, versión 1 (5 de noviembre de 2026). Lo aprueba quien figure como titular en `PROVEEDOR_RAZON_SOCIAL`.
Guía orientativa: antes de un lanzamiento público conviene revisarla con una persona abogada especializada.

## A. Protocolo ante una vulneración de seguridad (art. 38 de la Ley 19.670 y Decreto 64/020)

Una vulneración es cualquier acceso, pérdida, alteración o divulgación no autorizada de datos personales
(por ejemplo: base de datos expuesta, clave filtrada, cuenta de moderación tomada, correo enviado a quien no correspondía).

| Paso | Qué se hace | Quién | Plazo |
|---|---|---|---|
| 1. Detectar y registrar | Anotar en el registro de incidentes: fecha y hora, quién lo vio, qué pasó. Guardar capturas y registros del servidor (Render, Supabase). | Quien lo detecta | Al instante |
| 2. Contener | Cortar el acceso y **rotar claves**: contraseña y URL de la base (Supabase), `FLASK_SECRET_KEY`, `GROQ_API_KEY`, `BREVO_API_KEY`, claves VAPID. Cambiar `FLASK_SECRET_KEY` cierra todas las sesiones. **Ojo:** `CHAT_MASTER_KEY` no se rota sin antes descifrar y volver a cifrar los chats del asistente y los números de cuenta; si estuvo expuesta, hacerlo en ese orden. | Responsable técnico | Horas |
| 3. Evaluar | Qué datos y cuántas personas afecta; si había datos bancarios, contraseñas (solo hashes), chats cifrados o ubicaciones; si hay menores; si el acceso fue real o solo posible. | Responsable técnico y titular | Dentro de las primeras 24 h |
| 4. Notificar a la URCDP | Comunicar la vulneración a la Unidad Reguladora y de Control de Datos Personales por su formulario (gub.uy/urcdp). Contenido: qué pasó, datos y personas afectadas, medidas tomadas y contacto. | Titular | **72 horas desde que se constata** |
| 5. Informar a las personas | Si la afectación es significativa, avisar a las personas (correo y aviso en la app): qué pasó, qué datos, qué hacer (por ejemplo cambiar la contraseña) y cómo contactarnos. | Titular | Sin demora |
| 6. Cerrar | Informe final a la URCDP con causa, medidas adoptadas y mejoras; corregir la causa; actualizar este protocolo y `docs/legal/` si cambia algo. | Titular y equipo | Después del hecho |

Los proveedores que tratan datos por nuestra cuenta (Supabase, Render, Groq, Brevo) deben avisarnos de inmediato si sufren
una vulneración: se guarda esa obligación en sus condiciones de tratamiento de datos (ver sección 8 del documento de cumplimiento).

### Registro de incidentes (una fila por incidente)

| Fecha y hora | Qué pasó | Datos y personas afectadas | Medidas | Aviso a la URCDP (fecha) | Aviso a las personas | Cierre |
|---|---|---|---|---|---|---|
| | | | | | | |

## B. Protocolo para atender derechos (artículos 13 a 16 de la Ley 18.331)

Los pedidos llegan a `PROVEEDOR_EMAIL` (hoy ahora.que.app@gmail.com) o se resuelven desde el perfil de la persona.

1. **Registrar** el pedido el mismo día: fecha, quién lo hace, qué pide (acceso, rectificación, actualización, inclusión, supresión o impugnar una valoración).
2. **Verificar la identidad:** el pedido debe venir desde el correo de la cuenta o indicar el usuario y responderse a ese correo. Nunca enviar datos a otra dirección.
3. **Resolver:**
   - *Acceso:* la persona puede descargar sus datos desde **Perfil → Descargar mis datos**. Si pide algo que el archivo no trae, se arma a mano. Es gratuito (hasta una vez cada seis meses sin costo).
   - *Rectificación / actualización:* desde el perfil; si no puede, se hace a pedido.
   - *Supresión:* **Perfil → Eliminar mi cuenta** borra toda la información asociada (verificado en `migraciones/eliminar_cuenta.sql`).
   - *Impugnar una valoración:* no tomamos decisiones automatizadas sobre las personas; la IA solo sugiere planes.
4. **Responder dentro de los 5 días hábiles** desde el pedido (para el acceso, en ese mismo plazo; para el resto, el plazo legal).
5. **Archivar** el pedido y la respuesta. Si la persona no recibe respuesta o no está conforme, puede iniciar la **acción de habeas data** y reclamar ante la URCDP.

### Registro de pedidos de derechos

| Fecha del pedido | Persona (usuario) | Derecho | Identidad verificada | Respuesta (fecha) | Resultado |
|---|---|---|---|---|---|
| | | | | | |
