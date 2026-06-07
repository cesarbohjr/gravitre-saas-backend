"""Enterprise secrets encryption tests."""
from types import SimpleNamespace

from app.services.enterprise_secrets_service import encrypt_enterprise_secret, resolve_siem_secret


def test_encrypt_and_resolve_siem_secret():
    settings = SimpleNamespace(connector_secrets_encryption_key="a" * 64)
    encrypted = encrypt_enterprise_secret("super-secret", settings)
    resolved = resolve_siem_secret({"secretEnc": encrypted}, settings)
    assert resolved == "super-secret"


def test_resolve_legacy_plaintext_siem_secret():
    settings = SimpleNamespace(connector_secrets_encryption_key="a" * 64)
    resolved = resolve_siem_secret({"secret": "legacy-secret"}, settings)
    assert resolved == "legacy-secret"
