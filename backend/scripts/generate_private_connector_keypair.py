#!/usr/bin/env python3
"""Generate Ed25519 keypair for signing private connector bundles (STA-98)."""
from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Ed25519 keypair for private connector bundles")
    parser.add_argument("--out-dir", default=".", help="Directory to write private.pem and public.pem")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = out_dir / "private-connector-signing-private.pem"
    public_path = out_dir / "private-connector-signing-public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    print(f"Wrote {private_path}")
    print(f"Wrote {public_path}")
    print("Sign bundles with the private key; upload public PEM with each bundle to Gravitre.")


if __name__ == "__main__":
    main()
