#!/usr/bin/env python3
"""Summarize nightly hardening smokes and write platform.hardening_smoke.* audit row."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

ARTIFACTS = [
    ROOT / "docs" / "delivery" / "smoke-marketplace-production-latest.json",
    ROOT / "docs" / "delivery" / "smoke-ai-production-latest.json",
    ROOT / "docs" / "delivery" / "smoke-research-cascade-prod-latest.json",
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env"):
        if p.is_file():
            merged.update({k: v for k, v in dotenv_values(p).items() if v})
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"missing": True, "path": str(path.name)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"parse_error": True, "path": str(path.name)}


def artifact_ok(data: dict[str, Any]) -> bool:
    """Accept the three distinct smoke report shapes used by Lane D."""
    if data.get("missing") or data.get("parse_error"):
        return False
    if data.get("ok") is True:
        return True
    if data.get("pass") is True:
        return True
    verdict = str(data.get("verdict") or data.get("status") or "").upper()
    if verdict.startswith("PASS") or verdict == "OK":
        return True
    summary = data.get("summary")
    if isinstance(summary, dict):
        fail = summary.get("fail")
        passed = summary.get("pass")
        if fail == 0 and isinstance(passed, int) and passed > 0:
            return True
    return False


def main() -> int:
    env = load_env()
    from supabase import create_client

    from qa_signal_audit import write_platform_signal

    results = {p.name: _read(p) for p in ARTIFACTS}
    oks = [artifact_ok(data) for data in results.values()]
    passed = all(oks) and bool(oks)

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": list(results.keys()),
        "results": {
            name: {
                "ok": artifact_ok(data),
                "missing": bool(data.get("missing")),
                "parse_error": bool(data.get("parse_error")),
                "summary": data.get("summary"),
                "verdict": data.get("verdict") or data.get("status"),
                "pass": data.get("pass"),
                "ok_flag": data.get("ok"),
            }
            for name, data in results.items()
        },
        "verdict": "PASS" if passed else "PARTIAL",
    }
    out = ROOT / "docs" / "delivery" / "smoke-hardening-summary-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    write_platform_signal(
        sb,
        action="platform.hardening_smoke.completed" if passed else "platform.hardening_smoke.failed",
        verdict=report["verdict"],
        metadata=report,
        resource_id="hardening-smoke",
    )
    print(json.dumps({"verdict": report["verdict"], "out": str(out), "oks": oks}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
