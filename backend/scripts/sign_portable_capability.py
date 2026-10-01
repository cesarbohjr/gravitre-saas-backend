#!/usr/bin/env python3
"""Sign a portable Gravitre capability locally with an Ed25519 private key.

Private keys never leave the publisher machine. The output contains only the
detached base64 signature, public key PEM, and package metadata needed for upload.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.capabilities.importers import RESOURCE_SUFFIXES, SCRIPT_SUFFIXES, import_file_bundle
from app.capabilities.provenance import bundle_digest
from app.connectors.private.signature import bundle_message_digest


def collect_bundle_files(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise ValueError("Capability source root must be a directory")
    files: dict[str, str] = {}
    supported = set(RESOURCE_SUFFIXES) | set(SCRIPT_SUFFIXES)
    named = {"skill.md", "plugin.json", "gravitre-plugin.json", ".mcp.json", "mcp.json"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() not in supported and path.name.lower() not in named:
            continue
        try:
            files[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    if not files:
        raise ValueError("No supported capability source files found")
    return files


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Private key must be Ed25519")
    return key


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign a portable Gravitre capability")
    parser.add_argument("source_root", type=Path, help="Capability package directory")
    parser.add_argument("--private-key", required=True, type=Path, help="Ed25519 private key PEM")
    parser.add_argument("--output", type=Path, help="Optional JSON output file")
    args = parser.parse_args()

    files = collect_bundle_files(args.source_root.resolve())
    bundle = import_file_bundle(files)
    key = load_private_key(args.private_key.resolve())
    signature = key.sign(bundle_message_digest(bundle.manifest, files))
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    payload = {
        "name": bundle.inspection.name,
        "version": bundle.inspection.version,
        "contentDigest": bundle_digest(files),
        "signature": base64.b64encode(signature).decode("ascii"),
        "signingPublicKeyPem": public_key,
        "privateKeyIncluded": False,
    }
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
