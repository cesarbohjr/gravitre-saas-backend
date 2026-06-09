#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def get(path: str, key: str) -> str:
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def describe(val: str) -> str:
    if not val:
        return "MISSING"
    if val.startswith("sb_secret_"):
        return "WRONG: sb_secret API key"
    if val.startswith("sb_publishable_"):
        return "sb_publishable"
    if val.startswith("eyJ"):
        return f"jwt len={len(val)}"
    if val.endswith("==") and len(val) > 40:
        return f"legacy_jwt_secret len={len(val)}"
    return f"other len={len(val)}"


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    local_anon = get(str(repo / "backend" / ".env"), "SUPABASE_ANON_KEY")
    vercel_anon = get(str(repo / ".env.vercel.production"), "NEXT_PUBLIC_SUPABASE_ANON_KEY")
    local_jwt = get(str(repo / "backend" / ".env"), "SUPABASE_JWT_SECRET")
    vercel_jwt = get(str(repo / ".env.vercel.production"), "SUPABASE_JWT_SECRET")
    legacy = (
        "iEyare8jD2ZSmaxBLUEJtc143N4NHcds1LIfTM1/W7AF0GgZC1zoNr/4KXTBD42Ds3G+TV7k7QmE4P0JN9/34w=="
    )

    print("local_anon", describe(local_anon))
    print("vercel_anon", describe(vercel_anon))
    print("anon_match", local_anon == vercel_anon)
    print("local_jwt", describe(local_jwt))
    print("vercel_jwt", describe(vercel_jwt))
    print("local_jwt_matches_dashboard_legacy", local_jwt == legacy)
    print("vercel_jwt_matches_dashboard_legacy", vercel_jwt == legacy)


if __name__ == "__main__":
    main()
