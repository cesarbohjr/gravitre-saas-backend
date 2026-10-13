"""Acceptance tests for the cross-source context engine, offline and deterministic.

The harness (``harness.py``) runs the same synthetic queries for two orgs
through the real prompt assembly in shadow, active (production today) and
active-plus (new flags on) modes. These tests hold the properties the owner
asked to grade; the numbers in the audit report come from the same harness.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from tests.context_engine import harness as h
from tests.context_engine.golden import GOLDEN_PATH, snapshot


@pytest.fixture(scope="module")
def results() -> dict[str, dict[str, dict]]:
    return {
        f"{mode}/{surface}": h.run_cases(mode, spoken=spoken)
        for mode in h.MODES
        for surface, spoken in (("chat", False), ("voice", True))
    }


# --- flags off: production behaviour is unchanged ---------------------------


def test_flags_off_output_is_byte_identical_to_main() -> None:
    golden = json.loads(GOLDEN_PATH.read_text())
    assert snapshot() == golden
    # Explicitly false is the same as absent.
    assert snapshot(**{flag: False for flag in h.NEW_FLAGS}) == golden


# --- cross-source retrieval --------------------------------------------------


def test_cross_source_retrieval_merges_org_documents_and_packs(results) -> None:
    block = results["active/chat"]["sla"]["block"]
    assert "ORG PRIVATE KNOWLEDGE" in block
    assert results["active/chat"]["sla"]["coverage"] == 1.0
    account = results["active_plus/chat"]["account"]["block"]
    for kind in ("customer_quote", "account_interpretation", "account_measurement", "work_state"):
        assert f'type="{kind}"' in account, kind
    assert results["active_plus/chat"]["account"]["coverage"] == 1.0


def test_account_inputs_do_not_reach_the_prompt_in_production_today(results) -> None:
    assert results["active/chat"]["account"]["block"] == ""
    assert results["active/chat"]["account"]["coverage"] == 0.0


# --- context relevance (current over stale) ----------------------------------


def test_freshness_ranks_current_first_dates_sources_and_drops_expired(results) -> None:
    pricing = results["active_plus/chat"]["pricing"]["block"]
    assert pricing.index("$65") < pricing.index("$50")
    assert 'label="Pricing sheet 2026" as_of="' in pricing
    freeze = results["active_plus/chat"]["freeze"]
    assert freeze["stale"] == 0 and "expired" in freeze["excluded"]
    # Production today: the expired policy reaches the prompt with no date on it.
    assert results["active/chat"]["freeze"]["stale"] == 1
    assert "as_of=" not in results["active/chat"]["pricing"]["block"]


# --- deduplication -----------------------------------------------------------


def test_exact_duplicates_are_removed_in_active_and_near_duplicates_with_freshness(results) -> None:
    assert "duplicate" in results["active/chat"]["sla"]["excluded"]
    # Shadow serves the legacy prompt: the pack and the org document both appear.
    assert results["shadow/chat"]["sla"]["duplicates"] == 2
    assert results["active/chat"]["sla"]["duplicates"] == 1  # the HubSpot copy with a footer
    assert results["active_plus/chat"]["sla"]["duplicates"] == 0
    assert "near_duplicate" in results["active_plus/chat"]["sla"]["excluded"]


# --- sentiment grounding -----------------------------------------------------


def test_customer_words_and_inferences_are_labelled_apart(results) -> None:
    r = results["active_plus/chat"]["account"]
    assert r["attribution_errors"] == 0
    block = r["block"]
    assert "in their own words" in block
    assert "not statements the customer made" in block
    assert "not a customer statement and not a prediction" in block
    assert "PROPOSED by Gravitre; not approved and not started" in block


def test_colleague_messages_never_become_observations() -> None:
    from app.services.entity_observations import CustomerMessage, is_customer_facing

    org_domains = {"northwind.io"}
    colleague = CustomerMessage("we will cancel lol", "gmail", "email", "m1", h._ago(1), "pat@northwind.io")
    slack = CustomerMessage("customer is furious", "slack", "message", "m2", h._ago(1), "")
    customer = CustomerMessage("we will cancel", "gmail", "email", "m3", h._ago(1), "cto@acme.com")
    assert is_customer_facing(colleague, org_domains) == (False, "author_is_internal")
    assert is_customer_facing(slack, org_domains)[0] is False
    assert is_customer_facing(customer, org_domains) == (True, "")


# --- tenant isolation --------------------------------------------------------


def test_no_other_org_content_in_any_mode(results) -> None:
    for key, cases in results.items():
        for case_key, r in cases.items():
            assert r["foreign"] == 0, (key, case_key)


def test_every_account_read_is_org_scoped() -> None:
    from app.services.account_context_sources import build_account_context_sources

    class Recording(h.FakeClient):
        def __init__(self) -> None:
            super().__init__()
            self.unscoped: list[str] = []

        def table(self, name):
            q = super().table(name)
            original = q.execute
            filters: list[tuple[str, object]] = []
            eq = q.eq

            def _eq(col, val):
                filters.append((col, val))
                return eq(col, val)

            def _execute():
                scoped = any(c in {"org_id", "id"} and v == h.ORG_A for c, v in filters)
                if not scoped:
                    self.unscoped.append(name)
                return original()

            q.eq = _eq  # type: ignore[method-assign]
            q.execute = _execute  # type: ignore[method-assign]
            return q

    client = Recording()
    sources, _meta = build_account_context_sources(
        client, h.ORG_A, "how is Acme Corp?", spoken=False, settings=h.settings_for("active_plus")
    )
    assert sources and client.unscoped == []
    assert all("GLOBEX" not in s.content for s in sources)


# --- source revocation -------------------------------------------------------


def test_deleted_document_in_cached_retrieval_is_dropped_with_liveness(results) -> None:
    assert results["active/chat"]["discount"]["revoked"] == 1  # production today
    assert results["shadow/chat"]["discount"]["revoked"] == 1
    assert results["active_plus/chat"]["discount"]["revoked"] == 0


def test_revoked_connector_and_retracted_observations_never_resurface(results) -> None:
    assert results["active_plus/chat"]["account"]["revoked"] == 0
    assert results["active_plus/voice"]["account"]["revoked"] == 0


def test_consent_withdrawn_hides_observations_and_signals() -> None:
    tables = dict(h.TABLES)
    tables["organizations"] = [
        {"id": h.ORG_A, "settings": {"sourceDataGovernance": {"customerContext": {"enabled": False}}}}
    ]
    case = next(c for c in h.CASES if c.key == "account")

    async def _go():
        with ExitStack() as stack:
            h._patches(stack)
            return await h.build(case, h.settings_for("active_plus"), client=h.FakeClient(tables))

    block, meta = asyncio.run(_go())
    assert "not renewing" not in block and "days since the last customer message" not in block
    assert meta["accountSources"]["customerContextEnabled"] is False
    assert "PROPOSED by Gravitre" in block  # work state is the org's own data, not customer context


# --- context budgeting -------------------------------------------------------


def test_budget_is_respected_and_reported() -> None:
    async def _go():
        out = {}
        with ExitStack() as stack:
            h._patches(stack)
            for case in h.CASES:
                out[case.key] = await h.build(
                    case, h.settings_for("active_plus", cross_source_context_token_budget=600)
                )
        return out

    for key, (block, meta) in asyncio.run(_go()).items():
        ranking = meta.get("contextRanking") or {}
        if not ranking:
            continue
        assert ranking["tokensUsed"] <= 600, key
        assert len(block) // 4 <= 600 + 40, key  # heading text sits outside the ranked block


# --- chat / voice parity -----------------------------------------------------


def test_chat_and_voice_get_the_same_knowledge_and_voice_gets_no_quotes(results) -> None:
    for mode in h.MODES:
        for key in ("pricing", "sla", "discount", "freeze", "pricing_org_b"):
            assert results[f"{mode}/chat"][key]["block"] == results[f"{mode}/voice"][key]["block"], (mode, key)
    voice = results["active_plus/voice"]["account"]["block"]
    assert 'type="customer_quote"' not in voice
    assert "falling over 30 days" in voice and "PROPOSED by Gravitre" in voice


# --- shadow work when active is on -------------------------------------------


def test_active_with_shadow_on_ranks_once() -> None:
    from app.services.context_prioritization_engine import ContextPrioritizationEngine

    calls = {"n": 0}
    original = ContextPrioritizationEngine.build_context_profile

    def counting(self, **kwargs):
        calls["n"] += 1
        return original(self, **kwargs)

    case = next(c for c in h.CASES if c.key == "pricing")

    async def _go(settings):
        with ExitStack() as stack:
            h._patches(stack)
            stack.enter_context(patch.object(ContextPrioritizationEngine, "build_context_profile", counting))
            return await h.build(case, settings)

    asyncio.run(_go(h.settings_for("active")))
    assert calls["n"] == 1
    calls["n"] = 0
    asyncio.run(_go(h.settings_for("active", cross_source_context_engine_shadow_enabled=False)))
    assert calls["n"] == 1


# --- performance -------------------------------------------------------------


def test_selection_and_assembly_stay_cheap() -> None:
    # Generous ceiling for CI machines; the report records the measured numbers.
    for mode in ("active", "active_plus"):
        timing = h.time_cases(mode, iterations=5)
        assert timing["p95_ms"] < 250, (mode, timing)
