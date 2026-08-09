#!/usr/bin/env python3
"""Zip apps/extension for Chrome Web Store upload (excludes store drafts / dist)."""
from __future__ import annotations

import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "apps" / "extension"
OUT_DIR = SRC / "dist"
OUT = OUT_DIR / "gravitre-extension-chrome.zip"
SKIP_DIRS = {".git", "node_modules", "dist", "store", "__pycache__"}
SKIP_SUFFIXES = {".map", ".md"}


def main() -> int:
    if not (SRC / "manifest.json").is_file():
        raise SystemExit("apps/extension/manifest.json missing")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in SRC.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(SRC)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES and path.name != "README.md":
                # keep root README out of store zip; listing lives under store/
                continue
            if path.name == "README.md":
                continue
            zf.write(path, rel.as_posix())
            count += 1
    print(f"Wrote {OUT} ({count} files)")
    print("Upload in Chrome Developer Dashboard, then set NEXT_PUBLIC_CHROME_WEB_STORE_URL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
