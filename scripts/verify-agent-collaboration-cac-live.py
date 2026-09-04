#!/usr/bin/env python3
"""Honestly-labeled probe: Marketing → Finance CAC collaboration handoff.

Runs against production backend health + service-role Supabase for the isolated
org. Agent LLM turns are stubbed so the disagreement trail is deterministic;
handoff row + audit events are real DB writes when credentials are present.

Verdict labels:
  PASS — handoff row + collaboration audits + disagreement trail observed
  PARTIAL — local trail only (no prod DB write)
  FAIL — structural failure
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
OUT = REPO / "docs" / "delivery" / "agent-collaboration-cac-probe-live.json"
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
    import httpx

    env = _load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_kind": "probe_derived_deterministic_llm_stub",
        "scenario": (
            "Marketing projected CAC assumes 4.2% conversion; "
            "Finance challenges with historical healthcare 2.6%"
        ),
        "verdict": "FAIL",
    }

    try:
        health = httpx.get(f"{BASE}/health", timeout=30.0).json()
        report["api_git_sha"] = health.get("git_sha")
    except Exception as exc:  # noqa: BLE001
        report["api_git_sha"] = None
        report["health_error"] = str(exc)

    from app.config import get_settings
    from app.services.agent_collaboration_service import (
        COLLAB_AUDIT_CREATED,
        COLLAB_AUDIT_RECEIVER,
        COLLAB_AUDIT_RECONCILED,
        CollaborationTaskHandoff,
        assert_ranked_context_preserved,
        build_collaboration_briefing,
        build_ranked_context_for_handoff,
        execute_internal_collaboration_handoff,
    )
    from app.workflows.repository import get_supabase_client

    settings = get_settings()
    org_id = (env.get("ISOLATED_CONVERSATION_TEST_ORG_ID") or ISOLATED_ORG).strip()
    client = get_supabase_client(settings)

    agents = (
        client.table("agents")
        .select("id,name,department,status")
        .eq("org_id", org_id)
        .eq("status", "active")
        .limit(50)
        .execute()
    )
    rows = [dict(r) for r in (agents.data or [])]
    marketing = next(
        (a for a in rows if "market" in str(a.get("department") or a.get("name") or "").lower()),
        rows[0] if rows else None,
    )
    finance = next(
        (
            a
            for a in rows
            if a is not marketing
            and "financ" in str(a.get("department") or a.get("name") or "").lower()
        ),
        rows[1] if len(rows) > 1 else marketing,
    )
    report["agents_found"] = len(rows)
    report["marketing_agent_id"] = (marketing or {}).get("id")
    report["finance_agent_id"] = (finance or {}).get("id")

    if not marketing or not finance:
        report["verdict"] = "FAIL"
        report["error"] = "Need at least one active agent in isolated org"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    # Ensure department labels for observability even if DB rows omit them.
    marketing = {**marketing, "department": marketing.get("department") or "Marketing"}
    finance = {**finance, "department": finance.get("department") or "Finance"}

    ranked = build_ranked_context_for_handoff(
        task="Review Marketing CAC projection before budget approval",
        originating_claim={
            "claim": "Projected CAC assumes a 4.2% conversion rate",
            "projected_conversion_rate": 0.042,
            "channel": "healthcare paid search",
        },
        extra_sources=[
            {
                "source_id": "healthcare_hist",
                "source_type": "org_context",
                "label": "Historical healthcare conversion",
                "score": 0.98,
                "content": "Historical healthcare conversion is only 2.6%",
            }
        ],
    )
    handoff = CollaborationTaskHandoff(
        originating_agent_id=str(marketing["id"]),
        receiving_agent_id=str(finance["id"]),
        task="Review Marketing CAC projection before budget approval",
        originating_claim={
            "claim": "Projected CAC assumes a 4.2% conversion rate",
            "projected_conversion_rate": 0.042,
        },
        ranked_context=ranked,
        originating_department="Marketing",
        receiving_department="Finance",
        originating_agent_name=str(marketing.get("name") or "Marketing"),
        receiving_agent_name=str(finance.get("name") or "Finance"),
        workflow_run_id=None,
    )
    briefing = build_collaboration_briefing(handoff)
    try:
        assert_ranked_context_preserved(
            briefing,
            required_source_ids=["healthcare_hist"],
            required_substrings=["2.6%", "4.2"],
        )
        report["mutation_precheck"] = "PASS"
    except AssertionError as exc:
        report["mutation_precheck"] = f"FAIL:{exc}"
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 1

    receiver_output = {
        "summary": "Challenge conversion assumption",
        "decision": {
            "stance": "challenge",
            "reasoning": (
                "Marketing's projected CAC assumes a 4.2% conversion rate; "
                "historical healthcare conversion is only 2.6%."
            ),
            "assumptions_challenged": ["projected_conversion_rate"],
            "recommendation": "Recalculate CAC at 2.6% before budget approval",
        },
        "confidence": 92,
    }
    reconcile_output = {
        "summary": "Revise claim",
        "decision": {
            "stance": "revise",
            "reasoning": "Accepted Finance challenge on conversion rate",
            "revised_claim": {"projected_conversion_rate": 0.026},
            "accepted_challenges": ["projected_conversion_rate"],
            "unresolved_disagreements": [],
        },
    }

    actor_id = str(env.get("PROBE_ACTOR_USER_ID") or uuid4())

    def _get_agent(_client, _org_id: str, agent_id: str):
        if str(agent_id) == str(marketing["id"]):
            return marketing
        if str(agent_id) == str(finance["id"]):
            return finance
        return None

    with patch(
        "app.services.agent_collaboration_service.get_agent",
        side_effect=_get_agent,
    ):
        with patch(
            "app.services.agent_collaboration_service.run_agent_task",
            new_callable=AsyncMock,
            side_effect=[receiver_output, reconcile_output],
        ):
            trail = await execute_internal_collaboration_handoff(
                settings,
                org_id=org_id,
                actor_id=actor_id,
                handoff=handoff,
                client=client,
            )

    report["trail"] = trail.model_dump()
    report["label"] = trail.label
    report["disagreement_visible"] = trail.disagreement_visible
    report["receiver_stance"] = trail.receiver_stance
    report["handoff_id"] = trail.handoff_id
    report["audit_actions"] = trail.audit_actions

    required = {COLLAB_AUDIT_CREATED, COLLAB_AUDIT_RECEIVER, COLLAB_AUDIT_RECONCILED}
    ok = (
        trail.label == "Marketing → Finance"
        and trail.disagreement_visible
        and trail.receiver_stance == "challenge"
        and required.issubset(set(trail.audit_actions))
        and bool(trail.handoff_id)
    )
    report["verdict"] = "PASS" if ok else "FAIL"
    report["evidence_note"] = (
        "Probe-derived: deterministic stubbed agent turns; real agent_handoffs insert + "
        "agent.collaboration.* audit_events when service role can write."
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "api_git_sha": report.get("api_git_sha"),
                "handoff_id": report.get("handoff_id"),
                "label": report.get("label"),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
