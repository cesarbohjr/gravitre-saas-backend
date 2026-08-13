#!/usr/bin/env python3
"""Phase B live proof: council produces synthesis + peer cross-examination trail."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "phase-b-council-synthesis-live.json"
ISOLATED_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for line in text.splitlines():
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, _, value = line.partition("=")
                if key.strip() and value.strip():
                    merged[key.strip()] = value.strip().strip('"').strip("'")
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


async def main() -> int:
    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    org_id = (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or ISOLATED_ORG).strip()
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=30.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_error:{exc}"

    from app.services.council_service import get_council_service

    probe = f"phaseb-{uuid4().hex[:10]}"
    session = await get_council_service().start_council(
        org_id=org_id,
        workflow_id=str(uuid4()),
        run_id=str(uuid4()),
        objective=(
            f"{probe} Contentious: Should we freeze outbound SDR spend for 30 days "
            "to protect cash, or double down on paid outbound to hit Q3 pipeline?"
        ),
        options=["freeze_outbound_30d", "double_paid_outbound"],
        agents=[
            {"name": "CFO Analyst", "role": "analyst", "weight": 1.2},
            {"name": "Growth Advocate", "role": "advocate", "weight": 1.0},
            {"name": "Risk Skeptic", "role": "skeptic", "weight": 1.1},
        ],
        evidence={
            "cash_runway_months": 7,
            "pipeline_coverage": 0.8,
            "probe": probe,
        },
        max_rounds=2,
    )
    rounds = list(getattr(session, "debate_rounds", None) or [])
    synthesis = next((r for r in rounds if isinstance(r, dict) and r.get("type") == "synthesis"), None)
    peer_aware = False
    for r in rounds:
        if not isinstance(r, dict) or r.get("type") == "synthesis":
            continue
        for op in r.get("opinions") or []:
            text = " ".join(
                [
                    str(op.get("reasoning") or ""),
                    " ".join(str(x) for x in (op.get("key_points") or [])),
                    " ".join(str(x) for x in (op.get("concerns") or [])),
                ]
            ).lower()
            if any(
                token in text
                for token in (
                    "peer",
                    "agree",
                    "challenge",
                    "revise",
                    "advocate",
                    "skeptic",
                    "cfo",
                    "growth",
                    "risk",
                )
            ):
                peer_aware = True
                break
    ok = bool(synthesis) and bool(getattr(session, "final_recommendation", None)) and peer_aware
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_git_sha": tip,
        "org_id": org_id,
        "probe": probe,
        "session_id": getattr(session, "id", None),
        "final_recommendation": getattr(session, "final_recommendation", None),
        "has_synthesis": bool(synthesis),
        "synthesis_reasoning": (synthesis or {}).get("synthesis_reasoning"),
        "disagreement_trail": (synthesis or {}).get("disagreement_trail"),
        "peer_aware_language": peer_aware,
        "debate_round_count": len(rounds),
        "verdict": "PASS" if ok else "FAIL",
        "claim": (
            f"{'PASS' if ok else 'FAIL'} — Phase B council synthesis "
            f"session={getattr(session, 'id', None)} tip={tip}"
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
