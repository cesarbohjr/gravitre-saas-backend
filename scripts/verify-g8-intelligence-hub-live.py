#!/usr/bin/env python3
"""G8 — Intelligence hub prod evidence battery (G4–G7 live verification).

Exercises canonical page-context, intelligence_hub chat SSE visualization, and
trust-path contracts against production. Writes evidence to
docs/delivery/g8-intelligence-hub-live.json.

Usage:
  EXPECT_SHA=978a6a36 python scripts/verify-g8-intelligence-hub-live.py

Exit 0 = all runnable cases PASS. Exit 1 = any FAIL. Exit 2 = tip mismatch (skip).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    FORBIDDEN_OPERATOR_ORG_ID,
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)
from app.services.intelligence_context_compiler import FORBIDDEN_UNAVAILABLE_AGENT_PHRASES  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "g8-intelligence-hub-live.json"
CHAT_TIMEOUT = 120.0
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
LENSES = ("knows", "learns", "predicts", "acts", "improves")
TRUST_AGENT_SUBSTR = (os.environ.get("INTELLIGENCE_TRUST_AGENT_NAME") or "Email Campaign").lower()

CHAT_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "g1-g4-active-agents",
        "phase": "G1/G4",
        "message": "What agents are currently active?",
        "expect_lens": "acts",
        "expect_deterministic": True,
        "forbidden_phrases": list(FORBIDDEN_UNAVAILABLE_AGENT_PHRASES),
        "must_include_any": ("agent", "none configured", "no configured"),
    },
    {
        "id": "g4-predictions-attention",
        "phase": "G4/G6",
        "message": "What predictions need attention?",
        "expect_lens": "predicts",
        "expect_deterministic": True,
        "must_include_any": ("prediction", "no scoped", "attention", "none"),
    },
    {
        "id": "g4-g7-recent-learning",
        "phase": "G4/G7",
        "message": "What has Gravitre learned recently?",
        "expect_lens": "learns",
        "expect_deterministic": True,
        "must_include_any": ("learn", "insight", "none", "no validated", "business"),
    },
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in os.environ.items():
        if v and k not in merged:
            merged[k] = v
    for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if merged.get(k):
            os.environ[k] = merged[k]
    if not os.environ.get("SUPABASE_ANON_KEY"):
        os.environ["SUPABASE_ANON_KEY"] = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "anon-test")
    return merged


def parse_sse_intelligence(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    errors: list[str] = []
    visualizations: list[dict[str, Any]] = []
    answer_explanations: list[str] = []
    for block in re.split(r"\n\n+", raw or ""):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        typ = str(obj.get("type") or "")
        if typ in {"text-delta", "data-text-delta"}:
            texts.append(str(obj.get("delta") or obj.get("text") or ""))
        if typ == "error":
            errors.append(str(obj.get("errorText") or obj.get("error") or "error"))
        if typ == "data-intelligence":
            data = obj.get("data") if isinstance(obj.get("data"), dict) else obj
            if isinstance(data, dict):
                viz = data.get("visualization")
                if isinstance(viz, dict):
                    visualizations.append(viz)
                expl = data.get("answerExplanation")
                if expl:
                    answer_explanations.append(str(expl))
    return {
        "assistant": "".join(texts).strip(),
        "errors": errors,
        "visualizations": visualizations,
        "visualization": visualizations[-1] if visualizations else None,
        "answer_explanations": answer_explanations,
        "deterministic_path": any(
            "intelligence_hub:canonical" in e for e in answer_explanations
        ),
    }


def score_page_context(case_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    snapshot = ctx.get("snapshot") if isinstance(ctx.get("snapshot"), dict) else {}
    graph = ctx.get("graph") if isinstance(ctx.get("graph"), dict) else {}
    metrics = ctx.get("metrics") if isinstance(ctx.get("metrics"), dict) else {}
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []

    if case_id == "g3-page-context-all-lenses":
        lens = str(ctx.get("_lens") or "")
        checks["has_graph_nodes"] = isinstance(nodes, list)
        checks["has_graph_edges"] = isinstance(edges, list)
        checks["active_lens_matches"] = str(ctx.get("activeLens") or ctx.get("active_lens") or "") == lens
        checks["has_snapshot"] = bool(snapshot.get("generatedAt"))
        passed = all(checks.values())
        return {
            "passed": passed,
            "verdict": "PASS" if passed else "FAIL",
            "checks": checks,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    if case_id == "g6-metrics-semantics":
        execution = metrics.get("execution") if isinstance(metrics.get("execution"), dict) else {}
        checks["configured_active_key"] = "configuredActiveAgents" in execution
        checks["currently_running_key"] = "currentlyRunningAgents" in execution
        preds = snapshot.get("predictions") if isinstance(snapshot.get("predictions"), list) else []
        semantic_keys = [
            str(p.get("semanticKey") or "")
            for p in preds
            if isinstance(p, dict)
        ]
        checks["predictions_deduped"] = len(semantic_keys) == len(set(k for k in semantic_keys if k))
        passed = all(checks.values())
        return {"passed": passed, "verdict": "PASS" if passed else "FAIL", "checks": checks}

    if case_id == "g5-g7-inspector-evidence":
        preds = snapshot.get("predictions") if isinstance(snapshot.get("predictions"), list) else []
        learnings = snapshot.get("learnings") if isinstance(snapshot.get("learnings"), list) else []
        checks["predictions_have_evidence_field"] = all(
            "evidence" in p for p in preds if isinstance(p, dict)
        )
        checks["learnings_have_evidence_field"] = all(
            "evidence" in ln for ln in learnings if isinstance(ln, dict)
        )
        checks["learnings_have_business_statement"] = all(
            bool((ln or {}).get("businessStatement")) for ln in learnings if isinstance(ln, dict)
        )
        passed = all(checks.values())
        return {
            "passed": passed,
            "verdict": "PASS" if passed else "FAIL",
            "checks": checks,
            "prediction_count": len(preds),
            "learning_count": len(learnings),
        }

    if case_id == "g8-learning-map-focus":
        learnings = snapshot.get("learnings") if isinstance(snapshot.get("learnings"), list) else []
        learning_nodes = [
            n for n in nodes if isinstance(n, dict) and str(n.get("type") or "") == "learning"
        ]
        checks["learning_nodes_prefixed"] = all(
            str(n.get("id") or "").startswith("learning:") for n in learning_nodes
        )
        insight_ids = [
            str(ln.get("id") or "")
            for ln in learnings
            if isinstance(ln, dict) and ln.get("id")
        ]
        graph_ids = {str(n.get("id") or "") for n in learning_nodes}
        expected = {f"learning:{i}" if not i.startswith("learning:") else i for i in insight_ids}
        checks["graph_covers_insights"] = not insight_ids or expected.issubset(graph_ids)
        if not insight_ids and not learning_nodes:
            return {
                "passed": True,
                "verdict": "NOT RUN",
                "reason": "no learnings in canonical snapshot for isolated org",
                "checks": checks,
            }
        passed = all(checks.values())
        return {"passed": passed, "verdict": "PASS" if passed else "FAIL", "checks": checks}

    if case_id == "g3-knows-entity-nodes":
        snapshot = ctx.get("snapshot") if isinstance(ctx.get("snapshot"), dict) else {}
        entity_types = snapshot.get("knowledgeEntityTypes") or []
        entity_nodes = [
            n for n in nodes if isinstance(n, dict) and str(n.get("type") or "") == "entity"
        ]
        checks["snapshot_entity_types"] = isinstance(entity_types, list)
        if entity_types:
            checks["graph_has_entity_nodes"] = len(entity_nodes) > 0
            checks["entity_ids_prefixed"] = all(
                str(n.get("id") or "").startswith("entity:") for n in entity_nodes
            )
            expected = {f"entity:{et}" for et in entity_types}
            checks["graph_covers_types"] = expected.issubset({str(n.get("id") or "") for n in entity_nodes})
        else:
            checks["graph_has_entity_nodes"] = True
            checks["entity_ids_prefixed"] = True
            checks["graph_covers_types"] = True
        passed = all(checks.values())
        return {
            "passed": passed,
            "verdict": "PASS" if passed else "FAIL",
            "checks": checks,
            "entity_type_count": len(entity_types),
            "entity_node_count": len(entity_nodes),
        }

    return {"passed": False, "verdict": "FAIL", "error": f"unknown case {case_id}"}


def score_trust_org_context(ctx: dict[str, Any]) -> dict[str, Any]:
    snapshot = ctx.get("snapshot") if isinstance(ctx.get("snapshot"), dict) else {}
    agents = snapshot.get("agents") if isinstance(snapshot.get("agents"), list) else []
    metrics = ctx.get("metrics") if isinstance(ctx.get("metrics"), dict) else {}
    execution = metrics.get("execution") if isinstance(metrics.get("execution"), dict) else {}
    configured = int(execution.get("configuredActiveAgents") or 0)
    active = [a for a in agents if isinstance(a, dict) and a.get("isConfiguredActive")]
    labels = [str(a.get("businessLabel") or "") for a in active]
    trust_hit = any(TRUST_AGENT_SUBSTR in label.lower() for label in labels)
    return {
        "passed": len(active) == configured and (configured == 0 or trust_hit),
        "verdict": "PASS"
        if len(active) == configured and (configured == 0 or trust_hit)
        else "FAIL",
        "checks": {
            "metrics_match_roster": len(active) == configured,
            "trust_agent_present": trust_hit,
            "configured_active_agents": configured,
        },
        "active_agent_labels": labels[:8],
        "generated_at": snapshot.get("generatedAt"),
    }


def score_trust_org_learning(ctx: dict[str, Any]) -> dict[str, Any]:
    snapshot = ctx.get("snapshot") if isinstance(ctx.get("snapshot"), dict) else {}
    graph = ctx.get("graph") if isinstance(ctx.get("graph"), dict) else {}
    learnings = snapshot.get("learnings") if isinstance(snapshot.get("learnings"), list) else []
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    learning_nodes = [n for n in nodes if isinstance(n, dict) and str(n.get("type") or "") == "learning"]
    if not learnings:
        return {
            "passed": True,
            "verdict": "NOT RUN",
            "reason": "no promoted learnings in trust org snapshot",
        }
    insight_ids = {str(ln.get("id") or "") for ln in learnings if isinstance(ln, dict)}
    expected = {f"learning:{i}" if not i.startswith("learning:") else i for i in insight_ids if i}
    graph_ids = {str(n.get("id") or "") for n in learning_nodes}
    passed = expected.issubset(graph_ids) and all(
        str(n.get("id") or "").startswith("learning:") for n in learning_nodes
    )
    return {
        "passed": passed,
        "verdict": "PASS" if passed else "FAIL",
        "learning_count": len(learnings),
        "learning_node_count": len(learning_nodes),
        "checks": {
            "learning_nodes_prefixed": all(
                str(n.get("id") or "").startswith("learning:") for n in learning_nodes
            ),
            "graph_covers_insights": expected.issubset(graph_ids),
        },
    }


def resolve_trust_org_actor(env: dict[str, str], sb: Any) -> tuple[str, str, str] | None:
    org_id = (env.get("OPERATOR_ORG_ID") or FORBIDDEN_OPERATOR_ORG_ID).strip()
    user_id = (env.get("OPERATOR_USER_ID") or "").strip()
    email = (env.get("OPERATOR_EMAIL") or "").strip()
    if not user_id:
        members = (
            sb.table("organization_members")
            .select("user_id")
            .eq("org_id", org_id)
            .in_("role", ["admin", "owner"])
            .limit(1)
            .execute()
        ).data or []
        if members:
            user_id = str(members[0].get("user_id") or "")
    if not user_id:
        return None
    if not email:
        try:
            users = sb.auth.admin.get_user_by_id(user_id)
            email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
        except Exception:  # noqa: BLE001
            email = f"{user_id}@gravitre.local"
    return org_id, user_id, email


def auth_headers(env: dict[str, str], org_id: str, user_id: str, email: str) -> dict[str, str]:
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    return {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }


def score_chat_case(case: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    text = (turn.get("assistant") or "").lower()
    viz = turn.get("visualization") if isinstance(turn.get("visualization"), dict) else {}
    checks: dict[str, Any] = {
        "http_ok": int(turn.get("http_status") or 0) == 200,
        "has_assistant_text": bool(text.strip()),
        "has_visualization": bool(viz),
        "visualization_lens": viz.get("lens"),
        "deterministic_path": bool(turn.get("deterministic_path")),
        "no_sse_errors": not turn.get("errors"),
    }
    expect_lens = case.get("expect_lens")
    if expect_lens:
        checks["lens_matches"] = viz.get("lens") == expect_lens
    else:
        checks["lens_matches"] = True

    if case.get("expect_deterministic"):
        checks["deterministic_ok"] = bool(turn.get("deterministic_path"))
    else:
        checks["deterministic_ok"] = True

    forbidden = [p for p in (case.get("forbidden_phrases") or []) if p.lower() in text]
    checks["forbidden_hits"] = forbidden

    include = list(case.get("must_include_any") or [])
    checks["matched_include"] = True if not include else any(tok.lower() in text for tok in include)

    if expect_lens == "acts" and viz.get("highlightNodeIds"):
        checks["highlights_are_agent_ids"] = all(
            str(n).startswith("agent:") for n in viz.get("highlightNodeIds") or []
        )
    else:
        checks["highlights_are_agent_ids"] = True

    passed = (
        checks["http_ok"]
        and checks["has_assistant_text"]
        and checks["has_visualization"]
        and checks["lens_matches"]
        and checks["deterministic_ok"]
        and checks["matched_include"]
        and not forbidden
        and checks["no_sse_errors"]
        and checks["highlights_are_agent_ids"]
    )
    return {
        "passed": passed,
        "verdict": "PASS" if passed else "FAIL",
        "checks": checks,
        "assistant_excerpt": (turn.get("assistant") or "")[:400],
        "visualization": viz,
    }


async def fetch_page_context(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    lens: str,
) -> dict[str, Any]:
    r = await client.get(
        f"{BASE}/api/intelligence/page-context",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        params={"active_lens": lens, "window_hours": 24},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        data["_lens"] = lens
    return data if isinstance(data, dict) else {}


async def run_intelligence_hub_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    org_id: str,
    message: str,
) -> dict[str, Any]:
    cr = await client.post(
        f"{BASE}/api/conversations",
        headers={k: v for k, v in headers.items() if k != "Accept"},
        json={"title": f"g8-intel-{uuid.uuid4().hex[:8]}"},
        timeout=60,
    )
    cr.raise_for_status()
    conv_id = str(cr.json()["id"])
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": "fast",
        "conversation_id": conv_id,
        "spoken_mode": False,
        "surface": "intelligence_hub",
    }
    chunks: list[bytes] = []
    async with client.stream(
        "POST",
        f"{BASE}/api/assistant/chat",
        json=body,
        headers=headers,
        timeout=CHAT_TIMEOUT,
    ) as r:
        status = r.status_code
        async for part in r.aiter_bytes():
            chunks.append(part)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse_intelligence(raw)
    return {"conversation_id": conv_id, "http_status": status, **parsed}


async def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    org_id, user_id, email = resolve_isolated_conversation_actor(env, sb)
    url = env["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    headers = {
        **smoke_http_headers(),
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "probe": "g8_intelligence_hub_live",
        "started_at": utcnow(),
        "base": BASE,
        "org_id": org_id,
        "expect_sha": EXPECT_SHA,
        "cases": [],
    }

    async with httpx.AsyncClient() as client:
        health = (await client.get(f"{BASE}/health", timeout=30)).json()
        sha = str(health.get("git_sha") or "")
        report["git_sha"] = sha
        report["health_timestamp"] = health.get("timestamp")
        if EXPECT_SHA and not sha.startswith(EXPECT_SHA):
            report["verdict"] = f"NOT RUN — tip mismatch got={sha[:12]} expect={EXPECT_SHA}"
            OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"verdict": report["verdict"], "git_sha": sha}, indent=2))
            return 2

        # G3/G6/G7/G8 — page-context contract cases
        try:
            acts_ctx = await fetch_page_context(client, headers, "acts")
            report["page_context_sample"] = {
                "generated_at": (acts_ctx.get("snapshot") or {}).get("generatedAt"),
                "active_lens": acts_ctx.get("activeLens"),
            }
        except Exception as exc:  # noqa: BLE001
            acts_ctx = {}
            report["page_context_error"] = f"{exc.__class__.__name__}: {exc}"

        knows_ctx: dict[str, Any] = {}
        try:
            knows_ctx = await fetch_page_context(client, headers, "knows")
        except Exception:  # noqa: BLE001
            knows_ctx = {}

        static_cases = (
            ("g3-page-context-all-lenses", None),
            ("g3-knows-entity-nodes", knows_ctx),
            ("g6-metrics-semantics", acts_ctx),
            ("g5-g7-inspector-evidence", acts_ctx),
            ("g8-learning-map-focus", acts_ctx),
        )
        for case_id, ctx in static_cases:
            if case_id == "g3-page-context-all-lenses":
                lens_results = []
                all_ok = True
                for lens in LENSES:
                    try:
                        lens_ctx = await fetch_page_context(client, headers, lens)
                        scored = score_page_context(case_id, lens_ctx)
                        lens_results.append({"lens": lens, **scored})
                        all_ok = all_ok and scored.get("passed", False)
                    except Exception as exc:  # noqa: BLE001
                        lens_results.append(
                            {"lens": lens, "passed": False, "verdict": "FAIL", "error": str(exc)}
                        )
                        all_ok = False
                report["cases"].append(
                    {
                        "id": case_id,
                        "phase": "G3",
                        "passed": all_ok,
                        "verdict": "PASS" if all_ok else "FAIL",
                        "lens_results": lens_results,
                    }
                )
                continue

            if not ctx:
                report["cases"].append(
                    {
                        "id": case_id,
                        "passed": False,
                        "verdict": "FAIL",
                        "error": "page-context unavailable",
                    }
                )
                continue
            scored = score_page_context(case_id, ctx)
            phase = {
                "g3-knows-entity-nodes": "G3",
                "g6-metrics-semantics": "G6",
                "g5-g7-inspector-evidence": "G5/G7",
                "g8-learning-map-focus": "G8",
            }.get(case_id, "G?")
            report["cases"].append({"id": case_id, "phase": phase, **scored})

        # G1/G8 trust org — read-only page-context (no conversation writes)
        trust = resolve_trust_org_actor(env, sb)
        if trust:
            trust_org_id, trust_user_id, trust_email = trust
            trust_headers = auth_headers(env, trust_org_id, trust_user_id, trust_email)
            report["trust_org_id"] = trust_org_id
            try:
                trust_acts = await fetch_page_context(client, trust_headers, "acts")
                trust_learns = await fetch_page_context(client, trust_headers, "learns")
                report["cases"].append(
                    {
                        "id": "g1-trust-org-active-agents",
                        "phase": "G1",
                        **score_trust_org_context(trust_acts),
                    }
                )
                report["cases"].append(
                    {
                        "id": "g8-trust-org-learning-map",
                        "phase": "G8",
                        **score_trust_org_learning(trust_learns),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                report["cases"].append(
                    {
                        "id": "g1-trust-org-active-agents",
                        "phase": "G1",
                        "passed": False,
                        "verdict": "FAIL",
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )
        else:
            report["cases"].append(
                {
                    "id": "g1-trust-org-active-agents",
                    "phase": "G1",
                    "passed": True,
                    "verdict": "NOT RUN",
                    "reason": "OPERATOR_USER_ID not configured",
                }
            )

        # G4/G1 — intelligence_hub chat SSE visualization
        for case in CHAT_CASES:
            try:
                turn = await run_intelligence_hub_turn(
                    client, headers, org_id, str(case["message"])
                )
                scored = score_chat_case(case, turn)
                report["cases"].append(
                    {
                        "id": case["id"],
                        "phase": case["phase"],
                        "message": case["message"],
                        **scored,
                        "conversation_id": turn.get("conversation_id"),
                        "http_status": turn.get("http_status"),
                        "answer_explanations": turn.get("answer_explanations"),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                report["cases"].append(
                    {
                        "id": case["id"],
                        "phase": case.get("phase"),
                        "message": case.get("message"),
                        "passed": False,
                        "verdict": "FAIL",
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )

    runnable = [c for c in report["cases"] if c.get("verdict") != "NOT RUN"]
    all_pass = all(c.get("passed") for c in runnable)
    not_run = [c["id"] for c in report["cases"] if c.get("verdict") == "NOT RUN"]
    report["finished_at"] = utcnow()
    report["not_run_cases"] = not_run
    report["verdict"] = "PASS" if all_pass else "FAIL"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "git_sha": report.get("git_sha"),
                "cases": [
                    {"id": c["id"], "verdict": c.get("verdict"), "phase": c.get("phase")}
                    for c in report["cases"]
                ],
            },
            indent=2,
        )
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
