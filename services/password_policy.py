def validar_contrasena(password):
    """Devuelve un mensaje de error o None si cumple la política de seguridad."""
    if len(password or "") < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    return None
