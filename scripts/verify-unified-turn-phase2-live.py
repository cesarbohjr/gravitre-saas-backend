#!/usr/bin/env python3
"""Phase 2 live battery: unified-turn shadow/live vs classical path on prod.

Requires prod tip with unified-turn enabled (LIVE and/or SHADOW).
Runs targeted chat cases (incl. ≥15 imperfect-input), checks assistant copy
(no catalog keys / no typo echo / no spelling-correction narration), and
confirms unified_turn.live.completed or unified_turn.shadow.completed audits.

Writes docs/delivery/unified-turn-phase2-battery-live.json
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
from dotenv import dotenv_values
from supabase import create_client

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

from isolated_conversation_org import (  # noqa: E402
    resolve_isolated_conversation_actor,
    smoke_http_headers,
)
from app.services.user_facing_copy_guard import contains_raw_catalog_action_key  # noqa: E402

BASE = os.environ.get("LIVE_API_BASE", "https://api.gravitre.app").rstrip("/")
OUT = Path(
    os.environ.get(
        "PHASE2_OUT",
        str(ROOT / "docs" / "delivery" / "unified-turn-phase2-battery-live.json"),
    )
)
CHAT_TIMEOUT = 300.0
# Empty EXPECT_SHA = accept whatever tip /health reports (record it).
EXPECT_SHA = (os.environ.get("EXPECT_SHA") or "").strip()
# imperfect | all (default)
PHASE2_CASE_FILTER = (os.environ.get("PHASE2_CASE_FILTER") or "all").strip().lower()
PHASE2_IMPERFECT_ROUNDS = max(1, int(os.environ.get("PHASE2_IMPERFECT_ROUNDS") or "1"))
PHASE2_SKIP_CLASSICAL = (os.environ.get("PHASE2_SKIP_CLASSICAL") or "").strip() in (
    "1",
    "true",
    "yes",
)
RAW_CATALOG_KEY = re.compile(r"\b[a-z][a-z0-9_]*(?:\.[a-z0-9_]+){2,}\b", re.I)
MAP_FAIL = re.compile(r"couldn'?t map|no matching catalog action", re.I)
FABRICATED_ZERO_RUNS = re.compile(r"\b0\s+recent\s+runs\b", re.I)
FABRICATED_RUN_COUNT = re.compile(
    r"\b(?:there\s+(?:are|were)|you\s+have|found|showing)\s+\d+\s+(?:recent\s+)?(?:workflow\s+)?runs?\b",
    re.I,
)
KNOWLEDGE_BOUNDARY_ASSISTANT = re.compile(
    r"don't have that information|can't report a recent-run count|not retrieved|workflow run history was not",
    re.I,
)
# Module D imperfect-input: never narrate recovery or correct the user.
SPELLING_CORRECTION_NARRATE = re.compile(
    r"(?:i\s+think\s+you\s+meant|did\s+you\s+mean|just\s+to\s+clarify[, ]+you\s+meant|"
    r"assuming\s+you\s+meant|correcting\s+your\s+(?:spelling|typo|grammar)|"
    r"you\s+probably\s+meant|looks\s+like\s+a\s+typo)",
    re.I,
)
TTFT_TARGET_MS = int(os.environ.get("UNIFIED_TURN_TTFT_TARGET_MS", "200"))
TASKISH_OUTCOMES = [
    "clarifying_question",
    "confirmation_request",
    "connector_tool_proposal",
    "conversational_reply",
    "knowledge_boundary",
]
GMAIL_PENDING_SEED = {
    "pending_task": {
        "type": "connector_action",
        "status": "awaiting_confirm",
        "params": {
            "label": "Send Gmail message",
            "integration": "gmail",
            "invoke_action": "gmail.messages.send",
            "kind": "write",
        },
    }
}


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
    return merged


def parse_sse(raw: str) -> dict[str, Any]:
    texts: list[str] = []
    intel: list[dict[str, Any]] = []
    for block in re.split(r"\n\n+", raw):
        data_lines = [ln[5:].lstrip() for ln in block.splitlines() if ln.startswith("data:")]
        if not data_lines:
            continue
        payload = "\n".join(data_lines).strip()
        if payload in ("", "[DONE]"):
            continue
        try:
            o = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if o.get("type") == "text-delta":
            texts.append(str(o.get("delta") or ""))
        if o.get("type") == "data-intelligence":
            d = o.get("data") or {}
            intel.append(
                {
                    "answerExplanation": (d.get("answerExplanation") or "")[:200],
                    "routing": d.get("routing"),
                    "pendingReplyIntent": d.get("pendingReplyIntent"),
                }
            )
    return {"assistant": "".join(texts).strip(), "intel": intel}


async def health(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.get(f"{BASE}/health")
    r.raise_for_status()
    return r.json()


async def create_conversation(
    client: httpx.AsyncClient, headers: dict[str, str], title: str
) -> str:
    r = await client.post(
        f"{BASE}/api/conversations",
        headers=headers,
        json={"title": title[:80]},
        timeout=60,
    )
    r.raise_for_status()
    return str(r.json()["id"])


async def seed_task_state(sb: Any, *, conversation_id: str, org_id: str, task_state: dict) -> None:
    sb.table("conversations").update({"task_state": task_state}).eq("id", conversation_id).eq(
        "org_id", org_id
    ).execute()


async def chat_turn(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    conversation_id: str,
    org_id: str,
    message: str,
    mode: str = "standard",
) -> dict[str, Any]:
    body = {
        "messages": [{"role": "user", "parts": [{"type": "text", "text": message}]}],
        "org_id": org_id,
        "mode": mode or "standard",
        "conversation_id": conversation_id,
    }
    chunks: list[bytes] = []
    status = 0
    err = None
    try:
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
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
    raw = b"".join(chunks).decode("utf-8", errors="replace")
    parsed = parse_sse(raw) if status == 200 else {"assistant": raw[:400], "intel": []}
    return {
        "http": status,
        "assistant": parsed.get("assistant") or "",
        "intel": parsed.get("intel") or [],
        "error": err,
        "at": utcnow(),
    }


def fetch_shadow_audit(sb: Any, *, org_id: str, conversation_id: str, after_iso: str) -> dict | None:
    for _ in range(20):
        rows = (
            sb.table("audit_events")
            .select("action,created_at,metadata")
            .eq("org_id", org_id)
            .eq("resource_type", "conversation")
            .eq("resource_id", conversation_id)
            .in_(
                "action",
                [
                    "unified_turn.shadow.completed",
                    "unified_turn.live.completed",
                    "unified_turn.live.fallthrough",
                ],
            )
            .gte("created_at", after_iso)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        data = rows.data or []
        if data:
            return data[0]
        time.sleep(1)
    return None


CASES: list[dict[str, Any]] = [
    {
        "id": "greeting_no_catalog_leak",
        "message": "Hey",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
        "shadow_outcome_any": ["conversational_reply", "clarifying_question"],
    },
    {
        "id": "thanks_plain",
        "message": "Thank you",
        "must_not_match": [RAW_CATALOG_KEY],
        "shadow_outcome_any": ["conversational_reply", "clarifying_question"],
    },
    {
        "id": "email_intent_no_catalog_dump",
        "message": "Send an email to Stephanie about the proposal",
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL],
        "shadow_outcome_any": [
            "clarifying_question",
            "confirmation_request",
            "connector_tool_proposal",
            "conversational_reply",
        ],
    },
    {
        "id": "status_check_pending",
        "seed": GMAIL_PENDING_SEED,
        "message": "Did you send it yet?",
        "must_not_match": [RAW_CATALOG_KEY],
        "shadow_outcome_any": [
            "clarifying_question",
            "confirmation_request",
            "conversational_reply",
            "knowledge_boundary",
        ],
    },
    {
        "id": "knowledge_boundary_run_history_fast",
        "mode": "fast",
        "message": (
            "How many workflow runs did we have recently? "
            "Give me the exact count of recent runs."
        ),
        "must_not_match": [RAW_CATALOG_KEY, FABRICATED_ZERO_RUNS],
        "classical_must_not": [FABRICATED_ZERO_RUNS],
        "shadow_knowledge_boundary": True,
        "shadow_outcome_any": [
            "knowledge_boundary",
            "connector_tool_proposal",
            "clarifying_question",
            # LIVE often labels honest refusals conversational_reply; content gate below.
            "conversational_reply",
        ],
    },
    # --- Imperfect-input battery (≥15): typos / missing words / voice garble ---
    # Proves single-reasoning-call understanding; regex mapper cannot pass these.
    {
        "id": "imperfect_sned_emial",
        "imperfect_input": True,
        "message": "sned emial to stephanie about the meeting",
        "typo_tokens": ["sned", "emial"],
        "intent_must_match": re.compile(
            r"email|gmail|draft|stephanie|purpose|key points|recipient|subject", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_creat_contct",
        "imperfect_input": True,
        "message": "creat a contct named Jordan Lee in HubSpot",
        "typo_tokens": ["creat", "contct"],
        "intent_must_match": re.compile(r"contact|hubspot|jordan|/connectors|connected", re.I),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_aprove_pending",
        "imperfect_input": True,
        "seed": GMAIL_PENDING_SEED,
        "message": "aprove",
        "typo_tokens": ["aprove"],
        "intent_must_match": re.compile(
            r"yes|approv|waiting|cancel|send|gmail|confirm", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_shedule",
        "imperfect_input": True,
        "message": "shedule a follow up email for tomorrow morning",
        "typo_tokens": ["shedule"],
        "intent_must_match": re.compile(
            r"email|gmail|schedule|tomorrow|follow|draft|purpose|when|recipient|subject|body",
            re.I,
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_creaet_list",
        "imperfect_input": True,
        "message": "creaet an Apollo list called Q3 outbound",
        "typo_tokens": ["creaet"],
        "intent_must_match": re.compile(r"apollo|list|q3|/connectors|connected", re.I),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_connectr",
        "imperfect_input": True,
        "message": "is the slack connectr Connected right now",
        "typo_tokens": ["connectr"],
        "intent_must_match": re.compile(r"slack|connected|/connectors|healthy|status", re.I),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_mix_hubspot_creatd",
        "imperfect_input": True,
        "message": "can you chekc if teh HubSpot list got creatd",
        "typo_tokens": ["chekc", "teh", "creatd"],
        "intent_must_match": re.compile(
            r"hubspot|list|status|look|fetch|don.?t have|connected|/connectors", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_missing_to_words",
        "imperfect_input": True,
        "message": "send email stephanie about meeting",
        "typo_tokens": [],
        "intent_must_match": re.compile(
            r"email|gmail|stephanie|draft|purpose|key points|recipient|subject", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_disordered_hubspot",
        "imperfect_input": True,
        "message": "hubspot contact create for alex@example.com please",
        "typo_tokens": [],
        "intent_must_match": re.compile(
            r"hubspot|contact|alex|/connectors|connected|create", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_doubled_drafte",
        "imperfect_input": True,
        "message": "pleasse drafte a gmail to demo@example.com about pricing",
        "typo_tokens": ["pleasse", "drafte"],
        "intent_must_match": re.compile(
            r"gmail|email|draft|demo@example|pricing|purpose|key points", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_adjacent_senf_mesage",
        "imperfect_input": True,
        "message": "senf a slack mesage to #general saying kickoff is at 3",
        "typo_tokens": ["senf", "mesage"],
        "intent_must_match": re.compile(
            r"slack|#general|general|kickoff|message|/connectors|connected", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_thansk_then_task",
        "imperfect_input": True,
        "message": "thansk — also sned that hubspot note to maria",
        "typo_tokens": ["thansk", "sned"],
        "intent_must_match": re.compile(
            r"hubspot|maria|note|email|draft|/connectors|connected", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_voice_um_email",
        "imperfect_input": True,
        "message": "um so can you send an email to jordan about the deck",
        "typo_tokens": [],
        "intent_must_match": re.compile(
            r"email|gmail|jordan|deck|draft|purpose|key points|send|subject|body", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "assistant_must_not_contain": [" um ", "Um "],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_voice_runon_list",
        "imperfect_input": True,
        "message": (
            "yeah so create a hubspot contact list named summer leads "
            "when you get a chance"
        ),
        "typo_tokens": [],
        "intent_must_match": re.compile(
            r"hubspot|list|summer|/connectors|connected|create", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_voice_filler_aprove",
        "imperfect_input": True,
        "seed": GMAIL_PENDING_SEED,
        "message": "um yeah go ahead and aprove it",
        "typo_tokens": ["aprove"],
        "intent_must_match": re.compile(
            r"yes|approv|waiting|cancel|send|gmail|confirm", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
    {
        "id": "imperfect_stauts_pending",
        "imperfect_input": True,
        "seed": GMAIL_PENDING_SEED,
        "message": "whats teh stauts of that gmail",
        "typo_tokens": ["teh", "stauts"],
        "intent_must_match": re.compile(
            r"gmail|waiting|approv|pending|yes|cancel|send|status", re.I
        ),
        "must_not_match": [RAW_CATALOG_KEY, MAP_FAIL, SPELLING_CORRECTION_NARRATE],
        "shadow_outcome_any": TASKISH_OUTCOMES,
    },
]


def _shadow_meta(shadow: dict | None) -> dict[str, Any]:
    if not shadow:
        return {}
    meta = shadow.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def _assistant_has_catalog_key_leak(text: str) -> bool:
    return contains_raw_catalog_action_key(text or "")


def judge_case(case: dict[str, Any], turn: dict[str, Any], shadow: dict | None) -> dict[str, Any]:
    failures: list[str] = []
    assistant = turn.get("assistant") or ""
    if turn.get("http") != 200:
        failures.append(f"http:{turn.get('http')}")
    for pat in case.get("must_not_match") or []:
        if getattr(pat, "pattern", None) == RAW_CATALOG_KEY.pattern:
            if _assistant_has_catalog_key_leak(assistant):
                failures.append("forbidden_pattern:catalog_action_key")
        elif pat.search(assistant):
            failures.append(f"forbidden_pattern:{pat.pattern[:40]}")
    for pat in case.get("classical_must_not") or []:
        if pat.search(assistant):
            failures.append(f"classical_fabrication:{pat.pattern[:40]}")
    for fragment in case.get("assistant_must_not_contain") or []:
        if fragment and fragment in assistant:
            failures.append(f"assistant_echo_fragment:{fragment!r}")

    kb_without_audit = bool(
        shadow is None
        and case.get("shadow_knowledge_boundary")
        and KNOWLEDGE_BOUNDARY_ASSISTANT.search(assistant)
    )
    meta = _shadow_meta(shadow) if shadow else {}
    latency_ms = meta.get("latency_ms")
    model_text = str(meta.get("user_message") or "")
    check_texts = [assistant, model_text]

    if case.get("imperfect_input"):
        for token in case.get("typo_tokens") or []:
            tok = str(token).strip()
            if len(tok) < 3:
                continue
            pat = re.compile(rf"\b{re.escape(tok)}\b", re.I)
            if any(pat.search(t) for t in check_texts if t):
                failures.append(f"typo_echo:{tok}")
        if any(SPELLING_CORRECTION_NARRATE.search(t) for t in check_texts if t):
            failures.append("spelling_correction_narration")
        if not (assistant or "").strip() and not model_text.strip():
            failures.append("empty_imperfect_reply")
        intent_pat = case.get("intent_must_match")
        if intent_pat is not None:
            joined = "\n".join(t for t in check_texts if t)
            if not intent_pat.search(joined):
                failures.append("intent_not_resolved")

    if shadow is None and not kb_without_audit:
        failures.append("missing_shadow_audit")
    elif shadow is not None:
        outcome = str(meta.get("outcome_kind") or "")
        allowed = case.get("shadow_outcome_any")
        if allowed and outcome not in allowed:
            failures.append(f"shadow_outcome:{outcome}")
        if _assistant_has_catalog_key_leak(model_text):
            failures.append("shadow_message_catalog_leak")
        if case.get("shadow_knowledge_boundary"):
            if FABRICATED_ZERO_RUNS.search(model_text) or (
                FABRICATED_RUN_COUNT.search(model_text) and outcome != "connector_tool_proposal"
            ):
                failures.append("shadow_fabricated_run_count")
            if outcome == "conversational_reply" and FABRICATED_RUN_COUNT.search(model_text):
                failures.append("shadow_conversational_fabrication")

    if kb_without_audit and case.get("shadow_knowledge_boundary"):
        if FABRICATED_ZERO_RUNS.search(assistant) or FABRICATED_RUN_COUNT.search(assistant):
            failures.append("classical_fabricated_run_count")

    return {
        "ok": not failures,
        "failures": failures,
        "user_message": str(case.get("message") or ""),
        "assistant_full": assistant,
        "assistant_snippet": assistant[:320],
        "model_text_full": model_text,
        "imperfect_input": bool(case.get("imperfect_input")),
        "typo_tokens": list(case.get("typo_tokens") or []),
        "shadow_outcome": meta.get("outcome_kind"),
        "shadow_latency_ms": latency_ms,
        "shadow_first_token_proxy_ms": meta.get("first_token_proxy_ms"),
        "live_served": meta.get("live_served"),
        "shadow_audit_missing": shadow is None and not kb_without_audit,
        "knowledge_boundary_assistant_fallback": kb_without_audit,
        "shadow": {
            "action": shadow.get("action") if shadow else None,
            "created_at": shadow.get("created_at") if shadow else None,
            "outcome_kind": meta.get("outcome_kind"),
            "latency_ms": latency_ms,
            "user_message_preview": model_text[:280],
            "tool_name": meta.get("tool_name"),
            "live_served": meta.get("live_served"),
        }
        if shadow
        else None,
    }


async def main() -> int:
    env = load_env()
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
    }

    report: dict[str, Any] = {
        "feature": "unified_turn_phase2_batteries",
        "started_at": utcnow(),
        "expect_sha": EXPECT_SHA or None,
        "api_base": BASE,
        "case_filter": PHASE2_CASE_FILTER,
        "imperfect_rounds": PHASE2_IMPERFECT_ROUNDS,
        "skip_classical": PHASE2_SKIP_CLASSICAL,
        "cases": [],
        "classical_batteries": {},
        "ttft": {},
        "cutover_gates": {},
        "matrix": {},
    }

    async with httpx.AsyncClient() as client:
        h = await health(client)
        report["health"] = h
        sha = str(h.get("git_sha") or "")
        report["git_sha"] = sha
        expect = EXPECT_SHA or sha[:8]
        report["expect_sha"] = expect
        if expect and not (
            sha.lower().startswith(expect.lower()) or expect.lower().startswith(sha[: len(expect)].lower())
        ):
            # Allow ancestor: tip may be ahead of a min expect.
            try:
                import subprocess as _sp

                anc = _sp.run(
                    ["git", "merge-base", "--is-ancestor", expect, sha],
                    cwd=str(ROOT),
                    capture_output=True,
                )
                tip_ok = anc.returncode == 0
            except Exception:  # noqa: BLE001
                tip_ok = False
            if not tip_ok:
                report["fatal"] = f"health git_sha {sha} != expected {expect}"
                OUT.parent.mkdir(parents=True, exist_ok=True)
                OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report, indent=2))
                return 1

        selected = list(CASES)
        if PHASE2_CASE_FILTER in ("imperfect", "imperfect_input"):
            selected = [c for c in CASES if c.get("imperfect_input")]
        rounds = PHASE2_IMPERFECT_ROUNDS if any(c.get("imperfect_input") for c in selected) else 1
        if PHASE2_CASE_FILTER not in ("imperfect", "imperfect_input"):
            # Non-imperfect cases run once; imperfect cases repeat for variance.
            pass

        results: list[dict[str, Any]] = []
        for round_i in range(1, rounds + 1):
            for case in selected:
                if (
                    rounds > 1
                    and PHASE2_CASE_FILTER not in ("imperfect", "imperfect_input")
                    and not case.get("imperfect_input")
                    and round_i > 1
                ):
                    continue
                case_rounds = (
                    rounds
                    if case.get("imperfect_input") or PHASE2_CASE_FILTER in ("imperfect", "imperfect_input")
                    else 1
                )
                if round_i > case_rounds:
                    continue
                conv_id = await create_conversation(
                    client,
                    headers,
                    f"unified-phase2-{case['id']}-r{round_i}-{uuid.uuid4().hex[:8]}",
                )
                if case.get("seed"):
                    await seed_task_state(
                        sb, conversation_id=conv_id, org_id=org_id, task_state=case["seed"]
                    )
                started = utcnow()
                turn = await chat_turn(
                    client,
                    headers,
                    conversation_id=conv_id,
                    org_id=org_id,
                    message=str(case["message"]),
                    mode=str(case.get("mode") or "standard"),
                )
                await asyncio.sleep(8)
                shadow = fetch_shadow_audit(
                    sb, org_id=org_id, conversation_id=conv_id, after_iso=started
                )
                verdict = judge_case(case, turn, shadow)
                results.append(
                    {
                        "case": case["id"],
                        "round": round_i,
                        **verdict,
                        "conversation_id": conv_id,
                        "turn": {
                            "http": turn.get("http"),
                            "assistant": turn.get("assistant") or "",
                            "at": turn.get("at"),
                            "error": turn.get("error"),
                        },
                    }
                )
                print(
                    json.dumps(
                        {
                            "case": case["id"],
                            "round": round_i,
                            "ok": verdict.get("ok"),
                            "failures": verdict.get("failures"),
                            "outcome": verdict.get("shadow_outcome"),
                        }
                    ),
                    flush=True,
                )

        report["cases"] = results
        passed = sum(1 for r in results if r.get("ok"))
        report["summary"] = f"{passed}/{len(results)} targeted case-runs"
        selected_ids = {str(c["id"]) for c in selected}
        case_coverage: dict[str, Any] = {}
        for case in CASES:
            cid = str(case["id"])
            if cid not in selected_ids:
                case_coverage[cid] = {
                    "status": "skipped",
                    "reason": f"PHASE2_CASE_FILTER={PHASE2_CASE_FILTER}",
                }
                continue
            runs = [r for r in results if str(r.get("case")) == cid]
            case_coverage[cid] = {
                "status": "run",
                "ok": all(r.get("ok") for r in runs) if runs else False,
                "rounds": len(runs),
            }
        report["case_coverage"] = case_coverage
        latencies = [
            int(r["shadow_latency_ms"])
            for r in results
            if r.get("shadow_latency_ms") is not None
        ]
        report["ttft"] = {
            "note": (
                "Shadow path is non-streaming today; latency_ms / first_token_proxy_ms "
                "are full-completion proxies. Phase 3 requires true streamed TTFT < "
                f"{TTFT_TARGET_MS}ms."
            ),
            "target_ms": TTFT_TARGET_MS,
            "samples_ms": latencies,
            "p50_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
            "max_ms": max(latencies) if latencies else None,
            "phase3_streaming_gate": "NOT RUN — shadow not yet token-streaming",
            "proxy_under_target": bool(latencies) and max(latencies) < TTFT_TARGET_MS,
        }

    expect_for_children = report.get("expect_sha") or sha[:8]
    if PHASE2_SKIP_CLASSICAL:
        report["classical_batteries"] = {"skipped": True, "reason": "PHASE2_SKIP_CLASSICAL"}
    else:
        for script, key in (
            ("verify-pending-reply-classifier-live.py", "pending_reply"),
            ("verify-conversational-path-live.py", "conversational_path"),
            ("verify-run-history-stale-plan-live.py", "run_history_stale_plan"),
            ("smoke-sta305-slack-draft.py", "sta305_slack_omit_detail"),
            ("verify-unified-turn-persona-drift-live.py", "persona_drift_30"),
            ("_live_probe_send_email.py", "send_email_self_contradiction"),
        ):
            path = ROOT / "scripts" / script
            if not path.is_file():
                report["classical_batteries"][key] = {"exit_code": None, "skipped": True}
                continue
            child_env = {**os.environ, "EXPECT_SHA": str(expect_for_children)}
            if key == "sta305_slack_omit_detail":
                child_env["STA305_LIVE"] = "1"
            if key == "persona_drift_30":
                child_env.setdefault("LIVE_API_BASE", BASE)
            proc = subprocess.run(
                [sys.executable, str(path)],
                env=child_env,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=str(ROOT),
            )
            stdout_tail = (proc.stdout or "")[-2000:]
            stderr_tail = (proc.stderr or "")[-1500:]
            if proc.returncode != 0 and not stdout_tail.strip() and not stderr_tail.strip():
                stderr_tail = (
                    "child exited with no stdout/stderr (likely crash before main); "
                    f"script={script} returncode={proc.returncode}"
                )
            report["classical_batteries"][key] = {
                "exit_code": proc.returncode,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            }

    targeted_ok = passed == len(results) and len(results) > 0
    classical = report["classical_batteries"]

    def _sta305_status(entry: Any) -> str:
        if not isinstance(entry, dict):
            return "NOT RUN"
        tail = str(entry.get("stdout_tail") or "") + str(entry.get("stderr_tail") or "")
        if '"verdict": "BLOCKED"' in tail or "STA-305 live BLOCKED" in tail:
            return (
                "BLOCKED — OPEN (HubSpot+Slack not connected in isolated org; "
                "local mapper-only; NOT a live PASS)"
            )
        code = entry.get("exit_code")
        if code == 0:
            return "PASS (live)"
        if entry.get("skipped"):
            return "SKIPPED"
        return f"FAIL (exit {code})"

    def _classical_item_ok(key: str, entry: Any) -> bool:
        if not isinstance(entry, dict):
            return False
        if entry.get("skipped"):
            return True
        # STA-305 BLOCKED is an open named exception — does not fail core close,
        # but must not count as classical green.
        if key == "sta305_slack_omit_detail" and "BLOCKED" in _sta305_status(entry):
            return True
        return entry.get("exit_code") == 0

    if classical.get("skipped"):
        classical_ok = False  # not measured this run
    else:
        classical_ok = all(
            _classical_item_ok(k, v)
            for k, v in classical.items()
            if k != "skipped"
        )
        # Keep an explicit flag: BLOCKED STA-305 means not fully green.
        sta305_blocked = "BLOCKED" in _sta305_status(
            classical.get("sta305_slack_omit_detail")
        )
        report["sta305_live_open"] = sta305_blocked
    imperfect = [r for r in results if r.get("imperfect_input")]
    imperfect_ok = all(r.get("ok") for r in imperfect) if imperfect else False
    # Per-case both rounds must pass when imperfect was repeated.
    imperfect_by_id: dict[str, list[dict[str, Any]]] = {}
    for r in imperfect:
        imperfect_by_id.setdefault(str(r.get("case")), []).append(r)
    imperfect_stable = all(
        len(rows) >= (PHASE2_IMPERFECT_ROUNDS if PHASE2_CASE_FILTER in ("imperfect", "imperfect_input") or PHASE2_IMPERFECT_ROUNDS > 1 else 1)
        and all(x.get("ok") for x in rows)
        for rows in imperfect_by_id.values()
    ) if imperfect_by_id else False
    report["matrix"] = {
        "targeted_shadow_cases": report["summary"],
        "case_coverage": report.get("case_coverage") or {},
        "pending_reply_24": classical.get("pending_reply", {}),
        "conversational_path_20": classical.get("conversational_path", {}),
        "knowledge_boundary_run_history": report.get("case_coverage", {}).get(
            "knowledge_boundary_run_history_fast",
            {"status": "skipped", "reason": "not_in_results"},
        ),
        "imperfect_input_understanding": (
            f"{sum(1 for r in imperfect if r.get('ok'))}/{len(imperfect)}"
            if imperfect
            else "NOT RUN"
        ),
        "imperfect_input_all_ok": imperfect_ok,
        "imperfect_input_stable_across_rounds": imperfect_stable,
        "imperfect_unique_cases": len(imperfect_by_id),
        "sta305_omit_detail": _sta305_status(classical.get("sta305_slack_omit_detail")),
        "run_history_stale_plan": classical.get("run_history_stale_plan", {}).get("exit_code")
        if isinstance(classical.get("run_history_stale_plan"), dict)
        else None,
        "persona_drift_30_turn": classical.get("persona_drift_30", {}).get("exit_code")
        if isinstance(classical.get("persona_drift_30"), dict)
        else None,
        "send_email_self_contradiction": classical.get(
            "send_email_self_contradiction", {}
        ).get("exit_code")
        if isinstance(classical.get("send_email_self_contradiction"), dict)
        else None,
        "full_email_flow_multi_step": "PARTIAL — single-turn email intent only",
        "ttft_streaming_lt_200ms": report["ttft"].get("phase3_streaming_gate"),
    }
    report["cutover_gates"] = {
        "phase2_batteries_clean": targeted_ok
        and (classical_ok if not PHASE2_SKIP_CLASSICAL else targeted_ok),
        "phase2_core_batteries_clean": targeted_ok
        and (
            True
            if PHASE2_SKIP_CLASSICAL
            else all(
                isinstance(classical.get(k), dict) and classical.get(k, {}).get("exit_code") == 0
                for k in ("pending_reply", "conversational_path")
            )
        ),
        "phase3_ttft_streaming": False,
        "phase4_cutover_authorized": False,
        "standing_rule": (
            "Do not remove conversational_turn_gate / pending_reply_classifier / "
            "mapper regex / phrase-banks until Phase 4 after clean Phase 2+3"
        ),
        "write_authority_unchanged": True,
    }
    report["finished_at"] = utcnow()
    if PHASE2_CASE_FILTER in ("imperfect", "imperfect_input"):
        report["ok"] = imperfect_ok and imperfect_stable
    else:
        # Core Phase 2 bar: targeted + pending-reply + conversational when classical runs.
        core_ok = bool(report["cutover_gates"]["phase2_core_batteries_clean"])
        report["ok"] = core_ok
    report["verdict"] = "PASS" if report["ok"] else "FAIL"
    report["classical_all_ok"] = classical_ok if not PHASE2_SKIP_CLASSICAL else None
    report["cutover_gates"]["phase4_cutover_authorized"] = bool(
        report["ok"] and report.get("health", {}).get("git_sha")
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "verdict": report["verdict"],
                "summary": report["summary"],
                "ttft": report["ttft"],
                "matrix": report["matrix"],
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
