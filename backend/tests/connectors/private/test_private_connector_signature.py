"""Private connector bundle signature tests (STA-98)."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.connectors.private.signature import (
    BundleSignatureError,
    bundle_message_digest,
    verify_bundle_signature,
)

MANIFEST = json.loads(
    Path(__file__).resolve().parents[4].joinpath("docs/integration/examples/acme-tools/manifest.json").read_text(
        encoding="utf-8"
    )
)
SOURCES = {"handlers.py": "def tickets_list(ctx, params):\n    return {'success': True, 'data': {}}\n"}


def _sign(manifest: dict, sources: dict, private_key: Ed25519PrivateKey) -> tuple[str, str]:
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    message = bundle_message_digest(manifest, sources)
    signature = base64.b64encode(private_key.sign(message)).decode("ascii")
    return public_pem, signature


def test_verify_bundle_signature_accepts_valid_signature():
    private_key = Ed25519PrivateKey.generate()
    public_pem, signature = _sign(MANIFEST, SOURCES, private_key)
    verify_bundle_signature(
        manifest=MANIFEST,
        package_sources=SOURCES,
        signing_public_key_pem=public_pem,
        signature_b64=signature,
    )


def test_verify_bundle_signature_rejects_tampered_manifest():
    private_key = Ed25519PrivateKey.generate()
    public_pem, signature = _sign(MANIFEST, SOURCES, private_key)
    tampered = {**MANIFEST, "version": "9.9.9"}
    with pytest.raises(BundleSignatureError):
        verify_bundle_signature(
            manifest=tampered,
            package_sources=SOURCES,
            signing_public_key_pem=public_pem,
            signature_b64=signature,
        )
