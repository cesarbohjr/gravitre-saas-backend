#!/usr/bin/env python3
"""Probe Supabase /auth/v1/token without printing secrets."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.is_file():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"')
    return env


def merge_env(*paths: Path) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(load_env(path))
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def probe(name: str, url: str, anon: str, body: dict) -> None:
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/auth/v1/token",
        data=payload,
        method="POST",
        headers={
            "apikey": anon,
            "Authorization": f"Bearer {anon}",
            "Content-Type": "application/json",
        },
    )
    query = urllib.parse.urlencode({"grant_type": body.get("_grant") or "password"})
    req.full_url = f"{req.full_url}?{query}"
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"{name}: HTTP {resp.status}")
            print(resp.read().decode()[:400])
    except urllib.error.HTTPError as exc:
        print(f"{name}: HTTP {exc.code}")
        print(exc.read().decode()[:400])


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    env = merge_env(repo / "backend" / ".env", repo / "backend" / ".env.operator.local")
    url = env.get("SUPABASE_URL") or env.get("NEXT_PUBLIC_SUPABASE_URL") or ""
    anon = env.get("SUPABASE_ANON_KEY") or env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
    if not url or not anon:
        print("Missing SUPABASE_URL or anon key in backend/.env", file=sys.stderr)
        return 1

    print(f"project={url}")
    print(f"anon_format={'sb_*' if anon.startswith('sb_') else 'jwt' if anon.startswith('eyJ') else 'other'}")
    print(f"anon_len={len(anon)}")

    # Invalid credentials should return 400 invalid_grant, not 401 api key.
    probe(
        "password_invalid_creds",
        url,
        anon,
        {"email": "invalid@example.com", "password": "wrongpassword123", "_grant": "password"},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
