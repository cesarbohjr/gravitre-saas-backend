from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from app.capabilities.publisher_trust import public_key_fingerprint


def test_public_key_fingerprint_is_stable() -> None:
    key = Ed25519PrivateKey.generate().public_key()
    pem = key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    assert public_key_fingerprint(pem) == public_key_fingerprint(pem)
    assert public_key_fingerprint(pem).startswith("sha256:")
