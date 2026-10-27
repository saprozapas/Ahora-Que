"""Genera claves VAPID: guarda la privada en un PEM ignorado por Git e imprime .env."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main():
    privada = ec.generate_private_key(ec.SECP256R1())
    pem = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    publica = privada.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    publica_b64 = base64.urlsafe_b64encode(publica).rstrip(b"=").decode("ascii")
    archivo_privado = Path("vapid_private.pem")
    archivo_privado.write_bytes(pem)

    print(f"Clave privada guardada en {archivo_privado.resolve()} (no la compartas ni la subas a Git).\n")
    print(f"VAPID_PUBLIC_KEY={publica_b64}")
    privada_der = privada.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    privada_b64 = base64.urlsafe_b64encode(privada_der).rstrip(b"=").decode("ascii")
    print(f"VAPID_PRIVATE_KEY={privada_b64}")
    print("VAPID_SUBJECT=mailto:tu-correo@dominio.com")


if __name__ == "__main__":
    main()
