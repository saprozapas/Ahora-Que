"""Cifrado en reposo de los mensajes del chatbot (Envelope Encryption).

Cada conversación tiene su propia clave de datos (DEK, AES-256). La DEK
se guarda en la base "envuelta" (cifrada) con la clave maestra (KEK),
que NO está en la base: sale de la variable de entorno CHAT_MASTER_KEY.

Formato de los blobs guardados: nonce (12 bytes) + ciphertext + tag (AES-GCM).

La KEK se lee recién la primera vez que se usa (no al importar), así la
app sigue levantando aunque la variable no esté configurada: solo falla
el chatbot, con un mensaje claro.

Para generar una clave maestra nueva:
    python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12
_kek = None


class ClaveMaestraFaltante(RuntimeError):
    pass


def _get_kek():
    global _kek
    if _kek is None:
        valor = os.environ.get("CHAT_MASTER_KEY", "e/ZlK4BYeAvdLMhh4EHab+gESeNNKrzhVHLRWl1AGcg=").strip()
        if not valor:
            raise ClaveMaestraFaltante(
                "Falta la variable de entorno CHAT_MASTER_KEY (32 bytes en base64)."
            )
        clave = base64.b64decode(valor)
        if len(clave) != 32:
            raise ClaveMaestraFaltante(
                "CHAT_MASTER_KEY tiene que ser de 32 bytes (AES-256) codificada en base64."
            )
        _kek = AESGCM(clave)
    return _kek


def nueva_dek() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def envolver_dek(dek: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(_NONCE_BYTES)
    return nonce + _get_kek().encrypt(nonce, dek, aad)


def desenvolver_dek(blob: bytes, aad: bytes) -> bytes:
    return _get_kek().decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], aad)


def cifrar(dek: bytes, texto: str, aad: bytes) -> bytes:
    nonce = os.urandom(_NONCE_BYTES)
    return nonce + AESGCM(dek).encrypt(nonce, texto.encode("utf-8"), aad)


def descifrar(dek: bytes, blob: bytes, aad: bytes) -> str:
    return AESGCM(dek).decrypt(blob[:_NONCE_BYTES], blob[_NONCE_BYTES:], aad).decode("utf-8")
