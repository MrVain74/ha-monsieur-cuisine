"""Ver-/Entschlüsselung für den Monsieur-Cuisine-Login.

Dieses Modul enthält die zwei Krypto-Funktionen, die der verschlüsselte
App-Login braucht (AES-256-CBC + PKCS7 für den Inhalt, RSA/PKCS1v15 zum
Verpacken des AES-Schlüssels, alles Base64).

>>> HIER DEN GEPRÜFTEN CODE AUS ``~/MCint`` EINSETZEN <<<
Ersetze die zwei Platzhalter-Funktionen unten durch deine in ``MCint``
getesteten Funktionen (identischer Code). Die ``import``-Zeilen oben sind
schon da – du musst also nur die beiden ``def``-Blöcke austauschen.

Signaturen (müssen so bleiben, der Rest der Integration ruft sie so auf):
  encrypt_login_payload(plaintext: bytes, public_key_b64: str)
      -> (payload_b64: str, iv_b64: str, x_app_aes: str, key: bytes)
  decrypt_login_response(payload_b64: str, iv_b64: str, key: bytes) -> bytes
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def encrypt_login_payload(plaintext, public_key_b64):
    key = os.urandom(32)
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext)
    padded_data += padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    public_key = serialization.load_der_public_key(base64.b64decode(public_key_b64))
    encrypted_key = public_key.encrypt( key, asym_padding.PKCS1v15() )
    payload_b64 = base64.b64encode(ct).decode()
    iv_b64 = base64.b64encode(iv).decode()
    x_app_aes = base64.b64encode(encrypted_key).decode()
    return payload_b64, iv_b64, x_app_aes, key

def decrypt_login_response(payload_b64, iv_b64, key):
    ct = base64.b64decode(payload_b64)
    iv = base64.b64decode(iv_b64)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded) + unpadder.finalize()
    return data