#!/usr/bin/env python3
"""Sign a private connector bundle manifest + sources (STA-98)."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.connectors.private.signature import bundle_message_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign private connector bundle payload")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--handlers", required=True, help="Path to handlers.py")
    parser.add_argument("--private-key", required=True, help="Path to Ed25519 private key PEM")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    handlers = Path(args.handlers).read_text(encoding="utf-8")
    private_pem = Path(args.private_key).read_bytes()
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("Private key must be Ed25519")

    sources = {"handlers.py": handlers}
    message = bundle_message_digest(manifest, sources)
    signature = base64.b64encode(private_key.sign(message)).decode("ascii")
    print(json.dumps({"signature": signature, "packageSources": sources}, indent=2))


if __name__ == "__main__":
    main()
