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


def test_provenance_does_not_equate_signature_with_publisher_verification() -> None:
    from app.capabilities.provenance import provenance_summary

    summary = provenance_summary(
        files={"SKILL.md": "---\nname: test\n---\n"},
        publisher_name="Acme",
        signature_status="verified",
        source_uri="https://github.com/acme/capabilities",
    )
    assert summary["signatureStatus"] == "verified"
    assert summary["publisherVerified"] is False
    assert summary["publisherTrusted"] is False
    assert summary["publisherTrustScope"] == "none"
