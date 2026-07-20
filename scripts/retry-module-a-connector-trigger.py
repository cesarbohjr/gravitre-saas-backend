#!/usr/bin/env python3
"""Retry connector_trigger path and merge into four-path artifact."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import dotenv_values  # noqa: E402
from isolated_conversation_org import resolve_isolated_conversation_actor  # noqa: E402


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    spec = importlib.util.spec_from_file_location(
        "four_path", ROOT / "scripts" / "verify-module-a-four-path-live.py"
    )
    assert spec and spec.loader
    four = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(four)

    from supabase import create_client
    from app.config import get_settings

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, _email = resolve_isolated_conversation_actor(env, client)
    settings = get_settings()

    out: dict = {"path": "connector_trigger", "fanout_complete": False}
    for attempt in range(1, 4):
        try:
            out = four.path_connector_trigger(client, org_id, user_id, settings)
            if out.get("fanout_complete"):
                break
        except Exception as exc:  # noqa: BLE001
            out = {
                "path": "connector_trigger",
                "error": str(exc),
                "fanout_complete": False,
                "attempt": attempt,
            }
        print(f"attempt={attempt} complete={out.get('fanout_complete')} err={out.get('error')}")

    art_path = ROOT / "docs/delivery/module-a-four-path-live.json"
    art = json.loads(art_path.read_text(encoding="utf-8"))
    art["verified_at"] = datetime.now(timezone.utc).isoformat()
    art["deployed_git_sha"] = "bc4c133dfc944c442f67329c5083427cbcfe8227"
    paths = [p for p in (art.get("paths") or []) if p.get("path") != "connector_trigger"]
    paths.append(out)
    art["paths"] = paths
    art["all_four_fanout_complete"] = all(bool(p.get("fanout_complete")) for p in paths)
    art_path.write_text(json.dumps(art, indent=2), encoding="utf-8")
    print(json.dumps({"connector_trigger": out, "all_four": art["all_four_fanout_complete"]}, indent=2))
    return 0 if art["all_four_fanout_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
