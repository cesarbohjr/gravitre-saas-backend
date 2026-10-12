"""Offline, deterministic harness for the cross-source context engine.

Runs the same synthetic queries for two orgs through the real
``build_unified_turn_knowledge_context`` (real ranking, dedup, budget, render,
retrieved-content guard and account sources) with retrieval and storage
replaced by in-memory fixtures. No network, no model calls.

Modes:

* ``shadow``: CROSS_SOURCE_CONTEXT_ENGINE_ENABLED=false, shadow on. The legacy
  prompt is served; the ranking only feeds diagnostics.
* ``active``: production as read on 2026-10-12 (active ranking on, shadow on,
  budget 12000, retrieved-content guard on, every 3.0 Plus flag off).
* ``active_plus``: ``active`` plus the new flags (liveness, freshness and the
  three account inputs).

What it measures per query and mode: required-evidence coverage, stale,
revoked and other-org evidence that reached the prompt, duplicate copies,
incorrect attribution, prompt tokens (chars / 4, the engine's estimator) and
the wall time of selection and assembly. Retrieval, network and model latency
are not part of it: retrieval is a fixture.

Run ``python -m tests.context_engine.harness [out.json]`` from ``backend/`` for the numbers.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import re
import statistics
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ORG_A = "00000000-0000-4000-8000-00000000000a"
ORG_B = "00000000-0000-4000-8000-00000000000b"
NOW = datetime.now(UTC)


def _ago(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Fixture world
# ---------------------------------------------------------------------------

# Org documents. ``cached`` documents are still in a cached retrieval result
# although the document was deleted (is_active false) after the cache filled.
DOCUMENTS: list[dict[str, Any]] = [
    {"id": "doc-a-price-2024", "org_id": ORG_A, "title": "Pricing sheet 2024", "is_active": True,
     "updated_at": _ago(700), "metadata": {},
     "content": "Northwind list price for the Pro plan is $50 per seat per month."},
    {"id": "doc-a-price-2026", "org_id": ORG_A, "title": "Pricing sheet 2026", "is_active": True,
     "updated_at": _ago(25), "metadata": {},
     "content": "Northwind list price for the Pro plan is $65 per seat per month, effective September 2026."},
    {"id": "doc-a-sla", "org_id": ORG_A, "title": "Support SLA", "is_active": True,
     "updated_at": _ago(120), "metadata": {},
     "content": "Support SLA: priority-one tickets get a first response within 1 hour, around the clock."},
    {"id": "doc-a-sla-copy", "org_id": ORG_A, "title": "HubSpot KB: Support SLA", "is_active": True,
     "updated_at": _ago(119), "metadata": {},
     "content": "Support SLA: priority-one tickets get a first response within 1 hour, around the clock. "
                "(Synced from HubSpot knowledge base.)"},
    {"id": "doc-a-discount", "org_id": ORG_A, "title": "Discount authority (deleted)", "is_active": False,
     "updated_at": _ago(3), "metadata": {},
     "content": "Discount authority: reps may give up to 40% discount without approval."},
    {"id": "doc-a-discount-current", "org_id": ORG_A, "title": "Discount policy", "is_active": True,
     "updated_at": _ago(2), "metadata": {},
     "content": "Discount policy: any discount above 10% needs approval from the sales director."},
    {"id": "doc-a-freeze", "org_id": ORG_A, "title": "Holiday freeze 2025", "is_active": True,
     "updated_at": _ago(300), "metadata": {"valid_until": _ago(280)},
     "content": "Holiday freeze policy: no production deploys between December 20 and January 5."},
    {"id": "doc-a-freeze-2026", "org_id": ORG_A, "title": "Release calendar 2026", "is_active": True,
     "updated_at": _ago(10), "metadata": {},
     "content": "Release calendar 2026: the holiday freeze policy this year covers December 22 to January 2."},
    {"id": "doc-b-price", "org_id": ORG_B, "title": "Globex price book", "is_active": True,
     "updated_at": _ago(30), "metadata": {},
     "content": "Globex list price for the Pro plan is $99 per seat per month. GLOBEX-ONLY-MARKER."},
    {"id": "doc-b-sla", "org_id": ORG_B, "title": "Globex SLA", "is_active": True,
     "updated_at": _ago(30), "metadata": {},
     "content": "Globex support SLA: priority-one tickets get a first response within 4 hours. GLOBEX-ONLY-MARKER."},
]

# Platform knowledge pack hits (same for both orgs; not tenant data).
PACK_HITS: dict[str, list[dict[str, Any]]] = {
    "sla": [
        {"kind": "knowledge_pack",
         "content": "Support SLA: priority-one tickets get a first response within 1 hour, around the clock.",
         "score": 0.72, "citation": "pack.support/sla-benchmarks", "source": "pack.support/sla-benchmarks",
         "authority_score": 0.6},
    ],
}

ENTITIES = [
    {"id": "ent-a-acme", "org_id": ORG_A, "display_name": "Acme Corp", "kind": "company", "evidence": []},
    {"id": "ent-b-acme", "org_id": ORG_B, "display_name": "Acme Corp", "kind": "company", "evidence": []},
]


def _observations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    quotes = [
        ("We are seriously considering not renewing in March.", "churn_risk_language", "explicit", -1.0),
        ("The SSO outage last week blocked our whole team again.", "support_friction", "severe", 1.0),
        ("Honestly this has been a frustrating quarter.", "sentiment", "negative", -1.0),
        ("Your onboarding team was great at the start.", "sentiment", "positive", 1.0),
        ("Still waiting on the export fix we were promised.", "sentiment", "negative", -1.0),
        ("Please escalate, we need this resolved now.", "sentiment", "negative", -1.0),
    ]
    days = [3, 6, 9, 20, 24, 27]
    for i, ((quote, dim, label, score), d) in enumerate(zip(quotes, days, strict=True)):
        rows.append({"id": f"obs-a-{i}", "org_id": ORG_A, "entity_id": "ent-a-acme", "dimension": dim,
                     "label": label, "score": score, "confidence": 0.82, "evidence_quote": quote,
                     "source_system": "hubspot", "source_record_id": f"email-{i}", "observed_at": _ago(d),
                     "status": "active", "correction": None})
    # Sentiment rows for every message so the trend has evidence (falling: positive early, negative late).
    for i, (d, s, lab) in enumerate([(28, 1.0, "positive"), (26, 1.0, "positive"), (21, 0.0, "neutral"),
                                     (8, -1.0, "negative"), (5, -1.0, "negative"), (2, -1.0, "negative")]):
        rows.append({"id": f"obs-a-s{i}", "org_id": ORG_A, "entity_id": "ent-a-acme", "dimension": "sentiment",
                     "label": lab, "score": s, "confidence": 0.8,
                     "evidence_quote": f"message {i} text" if lab == "neutral" else f"sentiment evidence {i}",
                     "source_system": "hubspot", "source_record_id": f"thread-{i}", "observed_at": _ago(d),
                     "status": "active", "correction": None})
    # From Zendesk, whose connector was deleted: must not resurface.
    rows.append({"id": "obs-a-zd", "org_id": ORG_A, "entity_id": "ent-a-acme", "dimension": "churn_risk_language",
                 "label": "explicit", "score": 1.0, "confidence": 0.9,
                 "evidence_quote": "ZENDESK-REVOKED-QUOTE we will cancel", "source_system": "zendesk",
                 "source_record_id": "ticket-9", "observed_at": _ago(4), "status": "active", "correction": None})
    # A retracted (human-corrected) observation.
    rows.append({"id": "obs-a-retracted", "org_id": ORG_A, "entity_id": "ent-a-acme", "dimension": "sentiment",
                 "label": "negative", "score": -1.0, "confidence": 0.7, "evidence_quote": "RETRACTED-QUOTE",
                 "source_system": "hubspot", "source_record_id": "email-r", "observed_at": _ago(4),
                 "status": "retracted", "correction": {"retracted": True}})
    # Other tenant's account of the same name.
    rows.append({"id": "obs-b-0", "org_id": ORG_B, "entity_id": "ent-b-acme", "dimension": "churn_risk_language",
                 "label": "explicit", "score": 1.0, "confidence": 0.9, "evidence_quote": "GLOBEX-ACME-QUOTE cancel",
                 "source_system": "hubspot", "source_record_id": "b-email", "observed_at": _ago(2),
                 "status": "active", "correction": None})
    return rows


TABLES: dict[str, list[dict[str, Any]]] = {
    "rag_documents": DOCUMENTS,
    "org_business_entities": ENTITIES,
    "entity_observations": _observations(),
    "entity_behavior_signals": [
        {"org_id": ORG_A, "entity_id": "ent-a-acme", "signal": "contact_gap_days", "value": 34,
         "baseline": None, "window_end": _ago(1), "evidence_count": 9},
        {"org_id": ORG_A, "entity_id": "ent-a-acme", "signal": "contact_volume_change", "value": 2.4,
         "baseline": 3, "window_end": _ago(1), "evidence_count": 9},
    ],
    "work_objects": [
        {"id": "wo-1", "org_id": ORG_A, "business_entity_id": "ent-a-acme", "title": "Offer a renewal discount",
         "status": "proposed", "goal_id": "goal-1", "updated_at": _ago(1)},
        {"id": "wo-2", "org_id": ORG_A, "business_entity_id": "ent-a-acme", "title": "Fix SSO login loop",
         "status": "completed", "goal_id": None, "updated_at": _ago(4)},
        {"id": "wo-b", "org_id": ORG_B, "business_entity_id": "ent-b-acme", "title": "GLOBEX-WORK-ITEM",
         "status": "in_progress", "goal_id": None, "updated_at": _ago(1)},
    ],
    "goals": [{"id": "goal-1", "org_id": ORG_A, "title": "Keep net revenue retention above 110%"}],
    "connectors": [
        {"org_id": ORG_A, "type": "hubspot", "vendor": "hubspot", "status": "active", "deleted_at": None},
        {"org_id": ORG_A, "type": "zendesk", "vendor": "zendesk", "status": "active", "deleted_at": _ago(1)},
        {"org_id": ORG_B, "type": "hubspot", "vendor": "hubspot", "status": "active", "deleted_at": None},
    ],
    "organizations": [
        {"id": ORG_A, "settings": {"sourceDataGovernance": {"customerContext": {"enabled": True, "connectors": []}}}},
        {"id": ORG_B, "settings": {"sourceDataGovernance": {"customerContext": {"enabled": True, "connectors": []}}}},
    ],
}


class _Query:
    def __init__(self, client: FakeClient, name: str) -> None:
        self._client = client
        self._name = name
        self._filters: list[Any] = []
        self._limit: int | None = None

    def select(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self._filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col: str, vals: list[Any]) -> _Query:
        allowed = set(vals)
        self._filters.append(lambda r: r.get(col) in allowed)
        return self

    def is_(self, col: str, val: Any) -> _Query:
        want = None if str(val).lower() == "null" else val
        self._filters.append(lambda r: r.get(col) == want)
        return self

    def gte(self, col: str, val: Any) -> _Query:
        self._filters.append(lambda r: str(r.get(col) or "") >= str(val))
        return self

    def order(self, *_a: Any, **_k: Any) -> _Query:
        return self

    def limit(self, n: int) -> _Query:
        self._limit = n
        return self

    def execute(self) -> SimpleNamespace:
        self._client.reads.append(self._name)
        rows = [dict(r) for r in self._client.tables.get(self._name, []) if all(f(r) for f in self._filters)]
        return SimpleNamespace(data=rows[: self._limit] if self._limit else rows)


class FakeClient:
    """Supabase-shaped, filter-respecting, in memory."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.tables = tables if tables is not None else TABLES
        self.reads: list[str] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


# ---------------------------------------------------------------------------
# Retrieval fixtures (the cached hybrid result, org-scoped by the RPC)
# ---------------------------------------------------------------------------

def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in {"the", "and", "what", "for", "our"}}


def _retrieve_rows(org_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    q = _terms(query)
    scored = []
    for d in DOCUMENTS:
        if d["org_id"] != org_id:
            continue
        overlap = len(q & _terms(d["content"]))
        if overlap:
            # Stale pricing scores slightly higher, as old documents often do.
            bonus = 0.05 if d["id"] == "doc-a-price-2024" else 0.0
            scored.append((round(0.5 + 0.08 * overlap + bonus, 4), d))
    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    rows = []
    for score, d in scored[:top_k]:
        rows.append({"id": f"chunk-{d['id']}", "chunk_id": f"chunk-{d['id']}", "content": d["content"],
                     "score": score, "title": d["title"], "document_id": d["id"],
                     "source_id": f"src-{d['org_id'][-1]}"})
    return rows


class FakeRagService:
    async def retrieve_chunks(self, org_id: str, query: str, top_k: int = 8, agent_id: str | None = None, **_: Any):
        from app.services.rag_service import Chunk

        rows = _retrieve_rows(org_id, query, top_k)
        return [Chunk(id=r["id"], content=r["content"], score=r["score"], source=r["title"]) for r in rows], {
            "cache_hit": True
        }

    async def retrieve_hybrid_rows(self, org_id: str, query: str, top_k: int = 8, agent_id: str | None = None, **_: Any):
        return _retrieve_rows(org_id, query, top_k), {"cache_hit": True}


async def _packs(**kwargs: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    query = str(kwargs.get("query") or "").lower()
    hits = PACK_HITS["sla"] if "sla" in query else []
    if not hits:
        return "", {"fabric_hit_count": 0}, []
    section = "PLATFORM KNOWLEDGE PACK EXCERPTS (authoritative; cite when used):\n" + "\n\n".join(
        f"- [{h['citation']}]\n{h['content']}" for h in hits
    )
    return section, {"fabric_hit_count": len(hits)}, [dict(h) for h in hits]


# ---------------------------------------------------------------------------
# Queries and expectations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Case:
    key: str
    org_id: str
    query: str
    required: tuple[str, ...]
    stale: tuple[str, ...] = ()
    revoked: tuple[str, ...] = ()
    foreign: tuple[str, ...] = ()
    dedupe: tuple[str, ...] = ()
    attribution: dict[str, str] = field(default_factory=dict)  # marker -> expected source label
    chat_only: tuple[str, ...] = ()  # required in chat only (voice never reads quotes aloud)


CASES: tuple[Case, ...] = (
    Case("pricing", ORG_A, "What is the Pro plan list price per seat?", required=("$65",), stale=("$50",),
         foreign=("GLOBEX-ONLY-MARKER", "$99"), attribution={"$65": "Pricing sheet 2026"}),
    Case("sla", ORG_A, "What is our support SLA for priority-one tickets?", required=("within 1 hour",),
         foreign=("GLOBEX-ONLY-MARKER",), dedupe=("first response within 1 hour",)),
    Case("discount", ORG_A, "How much discount can reps give without approval?", required=("above 10%",),
         revoked=("40%",), attribution={"above 10%": "Discount policy"}),
    Case("freeze", ORG_A, "What is the holiday freeze policy for deploys?", required=("December 22",),
         stale=("December 20",)),
    Case("account", ORG_A, "How is Acme Corp doing, what have they said recently?",
         required=("not renewing in March", "falling over 30 days", "34", "PROPOSED by Gravitre"),
         chat_only=("not renewing in March",),
         revoked=("ZENDESK-REVOKED-QUOTE", "RETRACTED-QUOTE"),
         foreign=("GLOBEX-ACME-QUOTE", "GLOBEX-WORK-ITEM")),
    Case("pricing_org_b", ORG_B, "What is the Pro plan list price per seat?", required=("$99",),
         foreign=("Northwind", "$65", "$50")),
)

PROD_BASE: dict[str, Any] = {
    # Production as read on 2026-10-12 (audit run 38303179825): active ranking on,
    # shadow default on, budget default, retrieved-content guard on, 3.0 Plus flags off.
    "cross_source_context_engine_enabled": True,
    "cross_source_context_engine_shadow_enabled": True,
    "cross_source_context_token_budget": 12_000,
    "retrieved_content_guard_enabled": True,
    "evidence_sufficiency_loop_enabled": False,
    "evidence_sufficiency_max_rounds": 0,
    "evidence_contradiction_check_enabled": False,
    "internet_research_enabled": False,
    "entity_context_cards_enabled": False,
}
NEW_FLAGS = (
    "cross_source_context_liveness_v1",
    "cross_source_context_freshness_v1",
    "context_engine_observations_v1",
    "context_engine_account_signals_v1",
    "context_engine_work_state_v1",
)
MODES: dict[str, dict[str, Any]] = {
    "off": {**PROD_BASE, "cross_source_context_engine_enabled": False,
            "cross_source_context_engine_shadow_enabled": False},
    "shadow": {**PROD_BASE, "cross_source_context_engine_enabled": False},
    "active": dict(PROD_BASE),
    "active_plus": {**PROD_BASE, **{f: True for f in NEW_FLAGS}},
}


def settings_for(mode: str, **overrides: Any) -> SimpleNamespace:
    return SimpleNamespace(**{**MODES[mode], **overrides})


def _patches(stack: ExitStack) -> None:
    from app.services import adaptive_research_cascade as cascade
    from app.services import unified_turn_knowledge_context as ctx

    stack.enter_context(patch("app.services.rag_service.get_rag_service", lambda: FakeRagService()))
    stack.enter_context(patch.object(ctx, "_retrieve_knowledge_packs", _packs))
    stack.enter_context(patch.object(cascade, "assess_internal_retrieval_thinness", lambda **_: False))
    stack.enter_context(patch.object(cascade, "should_run_internet_research", lambda *a, **k: False))


async def build(case: Case, settings: Any, *, spoken: bool = False, client: FakeClient | None = None):
    from app.services.entity_context_card import clear_cache_for_tests
    from app.services.unified_turn_knowledge_context import (
        build_unified_turn_knowledge_context,
    )

    clear_cache_for_tests()
    kwargs: dict[str, Any] = {
        "org_id": case.org_id,
        "query": case.query,
        "client": client or FakeClient(),
        "settings": settings,
        "classification": {"department": "all", "intent": "knowledge_lookup"},
        "connected_integrations": ["hubspot"],
        "supplemental_context": {},
    }
    if "spoken_mode" in inspect.signature(build_unified_turn_knowledge_context).parameters:
        kwargs["spoken_mode"] = spoken
    return await build_unified_turn_knowledge_context(**kwargs)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(r'label="([^"]*)"|^- \[([^\]]*)\]', re.MULTILINE)


def label_before(block: str, index: int) -> str:
    last = ""
    for m in _LABEL_RE.finditer(block, 0, index):
        last = m.group(1) or m.group(2) or ""
    return last


def attribution_errors(block: str, case: Case) -> int:
    errors = 0
    for marker, expected in case.attribution.items():
        for m in re.finditer(re.escape(marker), block):
            if label_before(block, m.start()) != expected:
                errors += 1
    return errors


def account_statement_errors(block: str) -> int:
    """Inferred or measured content that is not inside a source saying so, or quotes not marked as the customer's."""
    errors = 0
    for m in re.finditer(r"(falling|rising|steady) over 30 days", block):
        src = block.rfind("<context_source", 0, m.start())
        if src < 0 or 'type="account_interpretation"' not in block[src: src + 200]:
            errors += 1
    for m in re.finditer(r"not renewing in March", block):
        src = block.rfind("<context_source", 0, m.start())
        if src < 0 or 'type="customer_quote"' not in block[src: src + 200]:
            errors += 1
    for m in re.finditer(r"Offer a renewal discount", block):
        line_end = block.find("\n", m.start())
        if "PROPOSED" not in block[m.start(): line_end if line_end > 0 else None]:
            errors += 1
    return errors


def score(case: Case, block: str, meta: dict[str, Any], *, spoken: bool = False) -> dict[str, Any]:
    required = [m for m in case.required if not (spoken and m in case.chat_only)]
    present = [m for m in required if m in block]
    duplicates = sum(max(0, block.count(m) - 1) for m in case.dedupe)
    ranking = meta.get("contextRanking") or {}
    return {
        "coverage": round(len(present) / len(required), 3) if required else 1.0,
        "missing": [m for m in required if m not in block],
        "stale": sum(1 for m in case.stale if m in block),
        "revoked": sum(1 for m in case.revoked if m in block),
        "foreign": sum(1 for m in case.foreign if m in block),
        "duplicates": duplicates,
        "attribution_errors": attribution_errors(block, case) + (account_statement_errors(block) if case.key == "account" else 0),
        "prompt_tokens": len(block) // 4,
        "ranking_mode": ranking.get("mode"),
        "selected": ranking.get("selectedCount"),
        "excluded": [e.get("reason") for e in ranking.get("excludedSources") or []],
    }


def run_cases(mode: str, *, spoken: bool = False, **overrides: Any) -> dict[str, dict[str, Any]]:
    async def _go() -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        with ExitStack() as stack:
            _patches(stack)
            for case in CASES:
                block, meta = await build(case, settings_for(mode, **overrides), spoken=spoken)
                out[case.key] = {**score(case, block, meta, spoken=spoken), "block": block}
        return out

    return asyncio.run(_go())


def time_cases(mode: str, *, spoken: bool = False, iterations: int = 40, **overrides: Any) -> dict[str, float]:
    """Wall time of selection and assembly per call (fixtures replace retrieval)."""

    async def _go() -> list[float]:
        samples: list[float] = []
        with ExitStack() as stack:
            _patches(stack)
            settings = settings_for(mode, **overrides)
            for case in CASES:  # warm-up
                await build(case, settings, spoken=spoken)
            for _ in range(iterations):
                for case in CASES:
                    t0 = time.perf_counter()
                    await build(case, settings, spoken=spoken)
                    samples.append((time.perf_counter() - t0) * 1000)
        return samples

    samples = sorted(asyncio.run(_go()))
    p95 = samples[min(len(samples) - 1, round(0.95 * (len(samples) - 1)))]
    return {"n": len(samples), "p50_ms": round(statistics.median(samples), 3), "p95_ms": round(p95, 3)}


def summary(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = list(results.values())
    return {
        "coverage": round(sum(r["coverage"] for r in rows) / len(rows), 3),
        "stale": sum(r["stale"] for r in rows),
        "revoked": sum(r["revoked"] for r in rows),
        "foreign": sum(r["foreign"] for r in rows),
        "duplicates": sum(r["duplicates"] for r in rows),
        "attribution_errors": sum(r["attribution_errors"] for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
    }


def main() -> None:
    report: dict[str, Any] = {}
    for mode in MODES:
        for surface, spoken in (("chat", False), ("voice", True)):
            results = run_cases(mode, spoken=spoken)
            report[f"{mode}/{surface}"] = {
                "summary": summary(results),
                "latency": time_cases(mode, spoken=spoken),
                "per_case": {k: {kk: vv for kk, vv in v.items() if kk != "block"} for k, v in results.items()},
            }
    text = json.dumps(report, indent=2, default=str)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
