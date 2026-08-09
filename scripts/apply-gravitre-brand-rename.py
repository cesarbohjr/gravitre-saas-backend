#!/usr/bin/env python3
"""One-shot Gravitree → Gravitre brand rename applicator (rg-driven file list)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_PATHS = {
    "docs/delivery/gravitre-routing-decision-map.md",
    "docs/delivery/gravitree-brand-rename-inventory-2026-08.md",
    "scripts/apply-gravitre-brand-rename.py",
    "scripts/check-gravitre-brand.mjs",
}


def transform(text: str) -> str:
    reps = [
        ("Gravitree", "Gravitre"),
        ("GRAVITREE_", "GRAVITRE_"),
        ("__GRAVITREE_", "__GRAVITRE_"),
        ("x-gravitree-", "x-gravitre-"),
        ("X-Gravitree-", "X-Gravitre-"),
        ("openInGravitreeUrl", "openInGravitreUrl"),
        ("activate-gravitree", "activate-gravitre"),
        ("activate_gravitree", "activate_gravitre"),
        ("__gravitreeOverlay", "__gravitreOverlay"),
        ("gravitree-overlay-root", "gravitre-overlay-root"),
        ("gravitree_managed", "gravitre_managed"),
        ("gravitree_smoke_run", "gravitre_smoke_run"),
        ("gravitree_request_actor", "gravitre_request_actor"),
        ("gravitree_voice", "gravitre_voice"),
        ("gravitree_connector_activation", "gravitre_connector_activation"),
        ("gravitree_test_client", "gravitre_test_client"),
        ("gravitree-loader", "gravitre-loader"),
        ("GravitreeLoader", "GravitreLoader"),
        ("GRAVITREE_AUTH", "GRAVITRE_AUTH"),
        ("module-d-gravitree-voice", "module-d-gravitre-voice"),
        ("gravitree-extension-chrome", "gravitre-extension-chrome"),
        ("/detail/gravitree/", "/detail/gravitre/"),
        ("gravitree.", "gravitre."),
        ("gravitree", "gravitre"),
        ("GRAVITREE", "GRAVITRE"),
    ]
    out = text
    for old, new in reps:
        out = out.replace(old, new)
    return out


def list_files() -> list[Path]:
    cmd = [
        "rg",
        "-i",
        "-l",
        "--glob",
        "!**/node_modules/**",
        "--glob",
        "!**/.git/**",
        "--glob",
        "!**/dist/**",
        "--glob",
        "!**/.next/**",
        "--glob",
        "!**/__pycache__/**",
        "--glob",
        "!**/coverage/**",
        "--glob",
        "!**/.cursor-tmp/**",
        "--glob",
        "!**/supabase/migrations/**",
        "gravitree",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    files: list[Path] = []
    for line in (proc.stdout or "").splitlines():
        rel = line.strip().replace("\\", "/")
        if not rel or rel in SKIP_PATHS:
            continue
        path = ROOT / rel
        if path.is_file():
            files.append(path)
    return files


def main() -> None:
    changed: list[str] = []
    for path in list_files():
        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        updated = transform(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(path.relative_to(ROOT).as_posix())

    renames = [
        (
            "apps/web/components/gravitre/gravitree-loader.tsx",
            "apps/web/components/gravitre/gravitre-loader.tsx",
        ),
        (
            "backend/app/services/gravitree_voice.py",
            "backend/app/services/gravitre_voice.py",
        ),
        (
            "backend/app/services/gravitree_connector_activation.py",
            "backend/app/services/gravitre_connector_activation.py",
        ),
        (
            "backend/tests/services/test_gravitree_voice.py",
            "backend/tests/services/test_gravitre_voice.py",
        ),
        (
            "docs/delivery/module-d-gravitree-voice.md",
            "docs/delivery/module-d-gravitre-voice.md",
        ),
        (
            "scripts/gravitree_test_client.py",
            "scripts/gravitre_test_client.py",
        ),
    ]
    for old_rel, new_rel in renames:
        old = ROOT / old_rel
        new = ROOT / new_rel
        if old.exists() and not new.exists():
            old.rename(new)
            changed.append(f"RENAME {old_rel} -> {new_rel}")

    print(f"updated_files={len(changed)}")
    for row in changed:
        print(row)


if __name__ == "__main__":
    main()
