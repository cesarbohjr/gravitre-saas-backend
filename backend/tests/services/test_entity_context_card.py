"""Phase 4: account cards in the turn context."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import entity_context_card as ecc

ORG = "org-1"
ON = SimpleNamespace(entity_context_cards_enabled=True)


class _Query:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def __getattr__(self, _name: str):
        return lambda *a, **k: self

    def execute(self):
        return SimpleNamespace(data=list(self._rows))


class _Client:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self.tables = tables
        self.calls: list[str] = []

    def table(self, name: str) -> _Query:
        self.calls.append(name)
        return _Query(self.tables.get(name, []))


def _ent(eid: str, name: str, host: str | None = None) -> dict[str, Any]:
    ev = [{"kind": "host", "value": host}] if host else []
    return {"id": eid, "display_name": name, "kind": "company", "evidence": ev}


def _obs(n: int, *, dim: str = "sentiment", start: float = 0.6, end: float = -0.6, label: str = "negative"):
    now = datetime.now(UTC)
    rows = []
    for i in range(n):
        score = start + (end - start) * i / max(1, n - 1)
        rows.append(
            {
                "dimension": dim,
                "label": label,
                "score": score,
                "evidence_quote": f"quote {i} about the renewal",
                "source_system": "hubspot",
                "source_record_id": f"e{i}",
                "observed_at": (now - timedelta(days=25 - i * 4)).isoformat(),
                "status": "active",
            }
        )
    return rows


@pytest.fixture(autouse=True)
def _clear():
    ecc.clear_cache_for_tests()
    yield
    ecc.clear_cache_for_tests()


def test_off_by_default_reads_nothing():
    c = _Client({"org_business_entities": [_ent("a", "Acme Corp")]})
    block, meta = ecc.build_entity_context_block(c, ORG, "how is Acme Corp?", spoken=False, settings=SimpleNamespace())
    assert block == "" and meta == {"skipped": "disabled"} and c.calls == []
    block, _ = ecc.build_entity_context_block(c, ORG, "Acme Corp", spoken=False, settings=MagicMock())
    assert block == ""


def test_match_is_word_bounded_by_name_or_host_and_longest_first():
    ents = [_ent("a", "Acme"), _ent("b", "Acme Europe"), _ent("c", "Globex", host="globex.io"), _ent("d", "Ion")]
    assert [r["id"] for r in ecc.match_accounts("update on acme europe please", ents)] == ["b", "a"]
    assert ecc.match_accounts("acmesoft is a different firm", ents) == []
    assert [r["id"] for r in ecc.match_accounts("emails from globex.io this week", ents)] == ["c"]
    # Names shorter than MIN_NAME_CHARS never match on their own.
    assert ecc.match_accounts("the ion team", ents) == []
    many = [_ent(str(i), f"Company{i}") for i in range(5)]
    assert len(ecc.match_accounts(" ".join(f"company{i}" for i in range(5)), many)) == ecc.MAX_ACCOUNTS


def test_text_card_shows_trend_systems_signals_and_quotes():
    c = _Client(
        {
            "org_business_entities": [_ent("a", "Acme Corp")],
            "org_business_entity_bindings": [{"system": "hubspot"}, {"system": "zendesk"}],
            "entity_observations": _obs(6),
            "entity_behavior_signals": [
                {"signal": "contact_volume_change", "value": 3.0, "baseline": 1.0, "window_end": "2026-10-11"}
            ],
        }
    )
    block, meta = ecc.build_entity_context_block(c, ORG, "What's going on with Acme Corp?", spoken=False, settings=ON)
    assert block.startswith(ecc.HEADER)
    assert "Acme Corp (in hubspot, zendesk)" in block
    assert "sentiment: falling" in block
    assert "3.0x its usual rate" in block
    assert '"quote 0 about the renewal"' in block
    assert len(block) <= ecc.TEXT_BUDGET_CHARS
    assert meta["accounts"] == ["a"] and meta["spoken"] is False


def test_voice_card_has_no_quotes_and_fits_spoken_budget():
    ents = [_ent("a", "Acme Corp"), _ent("b", "Globex Industries")]
    c = _Client(
        {
            "org_business_entities": ents,
            "org_business_entity_bindings": [{"system": "hubspot"}],
            "entity_observations": _obs(6) + _obs(6, dim="urgency", start=-0.5, end=0.9, label="high"),
            "entity_behavior_signals": [
                {"signal": "contact_volume_change", "value": 3.0, "window_end": "2026-10-11"},
                {"signal": "contact_gap_days", "value": 2.2, "window_end": "2026-10-11"},
            ],
        }
    )
    block, _ = ecc.build_entity_context_block(c, ORG, "compare acme corp and globex industries", spoken=True, settings=ON)
    assert block and '"' not in block
    assert len(block) <= ecc.SPOKEN_BUDGET_CHARS


def test_thin_evidence_is_left_out_not_shown_as_a_direction():
    c = _Client({"org_business_entities": [_ent("a", "Acme Corp")], "entity_observations": _obs(3)})
    block, _ = ecc.build_entity_context_block(c, ORG, "acme corp?", spoken=True, settings=ON)
    assert "falling" not in block and "rising" not in block
    assert "no observations with enough evidence yet" in block


def test_retracted_rows_are_ignored_and_no_match_or_error_is_empty():
    rows = _obs(6)
    for r in rows:
        r["status"] = "retracted"
    c = _Client({"org_business_entities": [_ent("a", "Acme Corp")], "entity_observations": rows})
    block, _ = ecc.build_entity_context_block(c, ORG, "acme corp", spoken=False, settings=ON)
    assert "falling" not in block and "about the renewal" not in block
    assert ecc.build_entity_context_block(c, ORG, "hello there", spoken=False, settings=ON) == (
        "",
        {"skipped": "no_account_named"},
    )
    broken = MagicMock()
    broken.table.side_effect = RuntimeError("db down")
    assert ecc.build_entity_context_block(broken, ORG, "acme corp", spoken=False, settings=ON) == (
        "",
        {"skipped": "error"},
    )


def test_entity_names_are_cached_per_org():
    c = _Client({"org_business_entities": [_ent("a", "Acme Corp")]})
    for _ in range(3):
        ecc.build_entity_context_block(c, ORG, "nothing named", spoken=False, settings=ON)
    assert c.calls.count("org_business_entities") == 1


async def _compile(settings: Any, client: Any, message: str, **kw):
    from app.services.context_compiler import compile_unified_reasoning_context

    with patch(
        "app.services.unified_turn_knowledge_context.build_unified_turn_knowledge_context",
        new_callable=AsyncMock,
        return_value=("", {"skipped": "test"}),
    ):
        return await compile_unified_reasoning_context(
            org_id=ORG,
            user_id="user-1",
            conversation_id="conv-1",
            message=message,
            task_state={},
            conversation_history=[],
            connected_integrations=["hubspot"],
            client=client,
            settings=settings,
            classification={"intent": "knowledge_lookup", "requires_action": False},
            cognitive_context=None,
            **kw,
        )


@pytest.mark.asyncio
async def test_compiler_includes_card_when_on_and_records_exclusion_when_off():
    from app.config import get_settings

    base = get_settings()
    on = base.model_copy(update={"entity_context_cards_enabled": True})
    c = _Client(
        {
            "org_business_entities": [_ent("a", "Acme Corp")],
            "entity_observations": _obs(6),
        }
    )
    compiled = await _compile(on, c, "How is Acme Corp doing?", spoken_mode=True)
    parts = dict(compiled.context_parts())
    assert "account_context" in parts and '"' not in parts["account_context"]
    assert any(d.source == "account_context" and d.action == "INCLUDE" for d in compiled.inclusion_decisions)

    off = await _compile(base, c, "How is Acme Corp doing?")
    assert "account_context" not in dict(off.context_parts())
    assert any(d.source == "account_context" and d.action == "EXCLUDE" for d in off.inclusion_decisions)
