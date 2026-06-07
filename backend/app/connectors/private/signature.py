"""Ed25519 signature verification for private connector bundles (STA-98)."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

BUNDLE_SIGNATURE_VERSION = "gravitre-private-bundle-v1"


class BundleSignatureError(ValueError):
    """Raised when a bundle signature is missing or invalid."""


def canonical_bundle_payload(manifest: dict[str, Any], package_sources: dict[str, str]) -> bytes:
    """Deterministic JSON bytes used for signing and verification."""
    payload = {
        "manifest": manifest,
        "sources": {key: package_sources[key] for key in sorted(package_sources.keys())},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def bundle_message_digest(manifest: dict[str, Any], package_sources: dict[str, str]) -> bytes:
    """Message signed by the enterprise private key."""
    digest = hashlib.sha256(canonical_bundle_payload(manifest, package_sources)).hexdigest()
    return f"{BUNDLE_SIGNATURE_VERSION}\n{digest}".encode("utf-8")


def load_ed25519_public_key(pem: str) -> Ed25519PublicKey:
    """Parse a PEM-encoded Ed25519 public key."""
    cleaned = (pem or "").strip()
    if not cleaned:
        raise BundleSignatureError(
            "Missing signing public key. Generate a keypair with "
            "backend/scripts/generate_private_connector_keypair.py and upload the public PEM."
        )
    try:
        key = serialization.load_pem_public_key(cleaned.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise BundleSignatureError(f"Invalid Ed25519 public key PEM: {exc}") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise BundleSignatureError("Signing key must be Ed25519")
    return key


def verify_bundle_signature(
    *,
    manifest: dict[str, Any],
    package_sources: dict[str, str],
    signing_public_key_pem: str,
    signature_b64: str,
) -> None:
    """Verify enterprise signature over the bundle payload."""
    public_key = load_ed25519_public_key(signing_public_key_pem)
    try:
        signature = base64.b64decode((signature_b64 or "").strip(), validate=True)
    except Exception as exc:  # noqa: BLE001
        raise BundleSignatureError("Signature must be base64-encoded Ed25519 bytes") from exc
    message = bundle_message_digest(manifest, package_sources)
    try:
        public_key.verify(signature, message)
    except InvalidSignature as exc:
        raise BundleSignatureError("Bundle signature verification failed") from exc
