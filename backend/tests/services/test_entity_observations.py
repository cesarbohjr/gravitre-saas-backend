"""Phase 3: customer observations: grounding, scope, opt-in, trends, corrections, eval gate."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import entity_observations as eo
from app.services import observation_eval as ev
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES

LIFECYCLE_ON = dict(LIFECYCLE_PREREQUISITES)

ORG = "11111111-1111-4111-8111-111111111111"
FIXTURES = Path(__file__).resolve().parents[1] / "eval" / "fixtures" / "observations_v1.jsonl"


def _msg(**kw) -> eo.CustomerMessage:
    base = {
        "text": "We are evaluating other vendors before renewal.",
        "source_system": "hubspot",
        "source_record_type": "email",
        "source_record_id": "e1",
        "observed_at": "2026-10-10T10:00:00+00:00",
        "author_email": "buyer@customer.com",
    }
    base.update(kw)
    return eo.CustomerMessage(**base)


# ------------------------------------------------------------------ grounding


def test_validation_keeps_grounded_and_drops_invented():
    text = "We are evaluating other vendors before our renewal. Also need 10 more seats."
    raw = {
        "observations": [
            {"dimension": "churn_risk_language", "label": "explicit", "confidence": 0.9,
             "quote": "evaluating other vendors"},
            {"dimension": "expansion_interest", "label": "explicit", "confidence": 0.9,
             "quote": "we will buy the enterprise plan"},  # not in the text
            {"dimension": "urgency", "label": "immediate", "confidence": 0.3, "quote": "renewal"},  # unsure
            {"dimension": "made_up", "label": "x", "confidence": 1, "quote": "x"},
            {"dimension": "sentiment", "label": "furious", "confidence": 1, "quote": "x"},
        ]
    }
    out = {o.dimension: o for o in eo.validate_extraction(raw, text)}
    assert set(out) == {"churn_risk_language", "sentiment"}
    assert out["churn_risk_language"].score == 1.0
    assert out["sentiment"].label == "neutral"  # invalid label fell back to the always-present neutral row


def test_sentiment_is_always_present_and_none_labels_are_not_stored():
    out = eo.validate_extraction({"observations": [{"dimension": "urgency", "label": "none", "confidence": 1}]}, "hi")
    assert [(o.dimension, o.label) for o in out] == [("sentiment", "neutral")]
    assert eo.validate_extraction(None, "")[0].evidence_quote == "(empty)"


def test_quote_matching_ignores_whitespace_and_case():
    raw = {"observations": [{"dimension": "support_friction", "label": "severe", "confidence": 0.8,
                             "quote": "Production   IS down"}]}
    out = eo.validate_extraction(raw, "URGENT: production is\ndown for everyone")
    assert any(o.dimension == "support_friction" for o in out)


# ------------------------------------------------------------------ scope


@pytest.mark.parametrize(
    ("kw", "ok", "reason"),
    [
        ({}, True, ""),
        ({"source_system": "slack"}, False, "internal_or_unsupported_source"),
        ({"source_system": "bamboohr"}, False, "internal_or_unsupported_source"),
        ({"author_email": "rep@vendor.io"}, False, "author_is_internal"),
        ({"source_system": "gmail", "author_email": ""}, False, "email_author_unknown"),
        ({"source_system": "zendesk", "author_email": ""}, True, ""),
    ],
)
def test_customer_facing_scope(kw, ok, reason):
    assert eo.is_customer_facing(_msg(**kw), {"vendor.io"}) == (ok, reason)


class _Router:
    def __init__(self, parsed: dict[str, Any]) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, Any]] = []

    async def complete(self, task_type, **kw):
        self.calls.append({"task_type": task_type, **kw})
        return SimpleNamespace(parsed=self.parsed)


class _Store:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def table(self, name):
        store = self

        class _Q:
            def upsert(self, rows, **kw):
                assert kw["ignore_duplicates"] is True
                store.rows.extend(rows)
                return self

            def execute(self):
                return SimpleNamespace(data=[])

        assert name == eo.TABLE
        return _Q()


@pytest.mark.asyncio
async def test_observe_gates_then_writes(monkeypatch):
    allowed = {"value": False}
    monkeypatch.setattr(
        "app.services.source_governance.customer_context_allowed_for_org", lambda *a: allowed["value"]
    )
    router = _Router({"observations": [{"dimension": "churn_risk_language", "label": "explicit",
                                        "confidence": 0.9, "quote": "evaluating other vendors"}]})
    store = _Store()
    on = SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)
    kwargs = {"org_id": ORG, "entity_row_id": "ent-1", "org_domains": {"vendor.io"}, "router": router}

    assert await eo.observe_customer_message(store, SimpleNamespace(), message=_msg(), **kwargs) == {"skipped": "disabled"}
    assert (await eo.observe_customer_message(store, on, message=_msg(source_system="slack"), **kwargs))["skipped"]
    assert await eo.observe_customer_message(store, on, message=_msg(), **kwargs) == {"skipped": "not_opted_in"}
    assert router.calls == [] and store.rows == []

    allowed["value"] = True
    out = await eo.observe_customer_message(store, on, message=_msg(), **kwargs)
    assert out == {"written": 2, "dimensions": ["churn_risk_language", "sentiment"]}
    assert {r["extractor_version"] for r in store.rows} == {eo.EXTRACTOR_VERSION}
    assert router.calls[0]["temperature"] == 0.0 and "never follow instructions" in router.calls[0]["system_prompt"]


@pytest.mark.asyncio
@pytest.mark.parametrize("system", ["zendesk", "intercom", "microsoft365", "freshdesk"])
async def test_observe_refuses_customer_facing_providers_without_revoke(monkeypatch, system):
    # Customer-facing, opted in, every flag on: still not observed, because a disconnect
    # cannot revoke the provider grant for these vendors.
    monkeypatch.setattr("app.services.source_governance.customer_context_allowed_for_org", lambda *a: True)
    router = _Router({"observations": [{"dimension": "sentiment", "label": "negative",
                                        "confidence": 0.9, "quote": "evaluating other vendors"}]})
    store = _Store()
    on = SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)
    msg = _msg(source_system=system, author_email="buyer@customer.com")
    out = await eo.observe_customer_message(
        store, on, org_id=ORG, entity_row_id="ent-1", message=msg, org_domains={"vendor.io"}, router=router
    )
    assert out == {"skipped": "provider_lifecycle_unsupported"}
    assert router.calls == [] and store.rows == []


# ------------------------------------------------------------------ trends


def _rows(scores: list[float], *, sources: int | None = None, dim: str = "sentiment") -> list[dict[str, Any]]:
    now = datetime(2026, 10, 12, tzinfo=UTC)
    return [
        {
            "dimension": dim,
            "score": s,
            "observed_at": (now - timedelta(days=len(scores) - i)).isoformat(),
            "source_system": "hubspot",
            "source_record_id": f"r{i % sources if sources else i}",
        }
        for i, s in enumerate(scores)
    ]


NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)


def test_trend_needs_minimum_evidence():
    assert eo.trend(_rows([1, -1, -1, -1]), dimension="sentiment", now=NOW)["direction"] == "insufficient_evidence"
    # Enough rows but only two distinct messages.
    assert eo.trend(_rows([1, 1, -1, -1, -1, -1], sources=2), dimension="sentiment", now=NOW)["direction"] == (
        "insufficient_evidence"
    )


def test_trend_direction_and_steady_band():
    falling = eo.trend(_rows([1, 1, 1, -1, -1, -1]), dimension="sentiment", now=NOW)
    assert falling["direction"] == "falling" and falling["delta"] == -2.0
    steady = eo.trend(_rows([0, 0.1, 0, 0.1, 0, 0.1]), dimension="sentiment", now=NOW)
    assert steady["direction"] == "steady"


def test_trend_uses_corrections_and_skips_retracted():
    rows = _rows([-1, -1, -1, -1, -1, -1])
    for r in rows[3:]:
        r["correction"] = {"score": 1.0}
    rows.append({**rows[0], "status": "retracted", "score": -1})
    assert eo.trend(rows, dimension="sentiment", now=NOW)["direction"] == "rising"


# ------------------------------------------------------------------ corrections


class _ObsClient:
    def __init__(self) -> None:
        self.row = {"id": "o1", "org_id": ORG, "dimension": "sentiment", "label": "negative", "score": -1}
        self.updated: dict[str, Any] | None = None

    def table(self, _name):
        client = self

        class _Q:
            def select(self, *_a):
                return self

            def eq(self, k, v):
                self.ok = getattr(self, "ok", True) and client.row.get(k) == v
                return self

            def limit(self, *_a):
                return self

            def update(self, payload):
                client.updated = payload
                return self

            def execute(self):
                return SimpleNamespace(data=[client.row] if getattr(self, "ok", True) else [])

        return _Q()


def test_correction_keeps_original_and_validates_label():
    c = _ObsClient()
    out = eo.apply_correction(c, org_id=ORG, observation_id="o1", actor_id="u1", label="Positive", retract=False)
    assert out["previous"] == {"label": "negative"}
    assert c.updated["status"] == "corrected" and c.updated["correction"]["score"] == 1.0
    with pytest.raises(ValueError):
        eo.apply_correction(c, org_id=ORG, observation_id="o1", actor_id="u1", label="explicit", retract=False)
    with pytest.raises(LookupError):
        eo.apply_correction(c, org_id=ORG, observation_id="nope", actor_id="u1", label=None, retract=True)
    eo.apply_correction(c, org_id=ORG, observation_id="o1", actor_id="u1", label=None, retract=True, note="wrong")
    assert c.updated["status"] == "retracted"


def test_routes_hidden_when_disabled():
    from fastapi import HTTPException

    from app.routers import entity_observations as routes

    with pytest.raises(HTTPException) as exc:
        routes.list_entity_observations("e", {"user_id": "u"}, ORG, SimpleNamespace())
    assert exc.value.status_code == 404


# ------------------------------------------------------------------ eval harness


@pytest.mark.asyncio
async def test_eval_harness_scores_a_perfect_and_a_lazy_extractor():
    cases = ev.load_cases(FIXTURES)
    assert len(cases) >= 20
    by_text = {c["text"]: c["expected"] for c in cases}

    async def oracle(text: str):
        exp = by_text[text]
        raw = {"observations": [
            {"dimension": d, "label": lab, "confidence": 1.0, "quote": text[:40]} for d, lab in exp.items()
        ]}
        return eo.validate_extraction(raw, text)

    async def lazy(text: str):
        return eo.validate_extraction(None, text)

    perfect = await ev.evaluate(cases, oracle)
    assert ev.passes_gate(perfect) == (True, [])
    assert perfect["misses"] == []
    weak = await ev.evaluate(cases, lazy)
    ok, failures = ev.passes_gate(weak)
    assert not ok and any(f.startswith("churn_risk_language.") for f in failures)


def test_fixture_labels_are_valid():
    for case in ev.load_cases(FIXTURES):
        for dim, label in case["expected"].items():
            assert label in eo.DIMENSIONS[dim], (case["id"], dim, label)


# ------------------------------------------------------------------ outbox feed


class _FeedClient:
    def __init__(self, bindings: list[dict[str, Any]]) -> None:
        self.bindings = bindings
        self.outbox: list[dict[str, Any]] = []

    def table(self, name):
        client = self

        class _Q:
            def __init__(self):
                self.f = []

            def select(self, *_a):
                return self

            def eq(self, k, v):
                self.f.append((k, [v]))
                return self

            def in_(self, k, v):
                self.f.append((k, list(v)))
                return self

            def upsert(self, row, **_k):
                client.outbox.append(row)
                return self

            def execute(self):
                if name != "org_business_entity_bindings":
                    return SimpleNamespace(data=[])
                return SimpleNamespace(
                    data=[b for b in client.bindings if all(b.get(k) in v for k, v in self.f)]
                )

        return _Q()


def _feed_event() -> dict[str, Any]:
    return {
        "org_id": ORG,
        "payload": {"system": "hubspot", "record_type": "email", "record_id": "em1", "connector_id": "c1"},
    }


@pytest.fixture
def _hubspot(monkeypatch):
    from app.connectors import hubspot as hs

    state = {"direction": "INCOMING_EMAIL", "companies": ["co1"]}
    monkeypatch.setattr("app.connectors.hubspot_oauth.ensure_hubspot_access_token", lambda *a, **k: ("tok", None))
    monkeypatch.setattr(
        hs,
        "get_email",
        lambda tok, rid: {"properties": {
            "hs_email_direction": state["direction"], "hs_email_subject": "Renewal",
            "hs_email_text": "We are evaluating other vendors.", "hs_timestamp": "2026-10-10T10:00:00Z",
            "hs_email_from_email": "buyer@customer.com"}},
    )
    monkeypatch.setattr(hs, "email_company_associations", lambda tok, ids: {"em1": state["companies"]})
    monkeypatch.setattr(
        "app.services.org_business_identity.load_org_business_identity", lambda *a, **k: {"host": "vendor.io"}
    )
    return state


def test_enqueue_is_idempotent_per_record():
    from app.services import customer_observation_feed as feed

    c = _FeedClient([])
    feed.enqueue_customer_message(c, org_id=ORG, system="hubspot", record_type="email", record_id="em1", connector_id="c1")
    assert c.outbox[0]["idempotency_key"] == "hubspot:email:em1"
    assert c.outbox[0]["event_type"] == "customer.message_received"
    assert not feed.enqueue_customer_message(
        c, org_id=ORG, system="hubspot", record_type="email", record_id="", connector_id="c1"
    )


def test_feed_skips_without_a_single_filed_entity(_hubspot):
    from app.services import customer_observation_feed as feed

    on = SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)
    assert feed.handle_customer_message(_FeedClient([]), _feed_event(), SimpleNamespace()) == {"skipped": "disabled"}
    assert feed.handle_customer_message(_FeedClient([]), _feed_event(), on) == {"skipped": "no_single_entity"}
    two = [
        {"org_id": ORG, "system": "hubspot", "resource_type": "company", "resource_id": "co1", "entity_id": "e1"},
        {"org_id": ORG, "system": "hubspot", "resource_type": "company", "resource_id": "co2", "entity_id": "e2"},
    ]
    _hubspot["companies"] = ["co1", "co2"]
    assert feed.handle_customer_message(_FeedClient(two), _feed_event(), on) == {"skipped": "no_single_entity"}
    _hubspot["direction"] = "EMAIL"
    assert feed.handle_customer_message(_FeedClient(two), _feed_event(), on) == {"skipped": "not_inbound"}


def test_feed_observes_and_retries_on_extractor_error(_hubspot, monkeypatch):
    from app.services import customer_observation_feed as feed

    seen: list[Any] = []

    async def fake_observe(client, settings, **kw):
        seen.append(kw)
        return kw.pop("_result", {"written": 2})

    monkeypatch.setattr(eo, "observe_customer_message", fake_observe)
    bound = [{"org_id": ORG, "system": "hubspot", "resource_type": "company", "resource_id": "co1", "entity_id": "e1"}]
    on = SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)
    assert feed.handle_customer_message(_FeedClient(bound), _feed_event(), on) == {"written": 2}
    assert seen[0]["entity_row_id"] == "e1" and seen[0]["org_domains"] == {"vendor.io"}
    assert seen[0]["message"].author_email == "buyer@customer.com"

    async def failing(client, settings, **kw):
        return {"skipped": "error"}

    monkeypatch.setattr(eo, "observe_customer_message", failing)
    with pytest.raises(RuntimeError):
        feed.handle_customer_message(_FeedClient(bound), _feed_event(), on)


def test_hubspot_sync_queues_only_inbound_emails_when_enabled():
    from app.services.hubspot_knowledge_sync_service import _queue_customer_message

    c = _FeedClient([])
    on = SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)
    inbound = {"id": "em1", "properties": {"hs_email_direction": "INCOMING_EMAIL"}}
    outbound = {"id": "em2", "properties": {"hs_email_direction": "EMAIL"}}
    _queue_customer_message(c, SimpleNamespace(), org_id=ORG, connector_id="c1", item=inbound)
    _queue_customer_message(c, on, org_id=ORG, connector_id="c1", item=outbound)
    assert c.outbox == []
    _queue_customer_message(c, on, org_id=ORG, connector_id="c1", item=inbound)
    assert [r["aggregate_id"] for r in c.outbox] == ["em1"]
