"""Lock recorded closed-slice latency envelopes. Does not re-run production."""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3] / "docs" / "delivery"

# Accepted ceilings. 10–30s on these paths is a regression. Not brittle exact ms.
_FIRST_USEFUL_MAX_MS = 8000
_COMPLETION_MAX_MS = 12000
_FOLLOWUP_FIRST_USEFUL_MAX_MS = 5000


def _load(name: str) -> dict:
    return json.loads((_ROOT / name).read_text(encoding="utf-8"))


def test_catalog_search_live_envelope_158c43eb() -> None:
    row = _load("gravitre-catalog-search-latency-live.json")
    assert str(row.get("health_sha") or "").startswith("158c43eb")
    assert int(row["first_useful_text_ms"]) <= _FIRST_USEFUL_MAX_MS
    assert int(row["completion_ms"]) <= _COMPLETION_MAX_MS
    assert row.get("search_knowledge_base") is False
    assert row.get("slo_5s_8s_met") is True


def test_class_c_listing_live_envelope() -> None:
    row = _load("gravitre-turn-latency-classes-live.json")
    sha = str(row.get("health_sha") or "")
    # Committed live file is Class C on 0b879ec4; c29f12cb is the preserve SHA in the matrix.
    assert sha.startswith("0b879ec4") or sha.startswith("c29f12cb")
    read = row["class_c_read"]
    assert int(read["first_useful_text_ms"]) <= _FIRST_USEFUL_MAX_MS
    assert int(read["completion_ms"]) <= _COMPLETION_MAX_MS
    assert read.get("create_claim") is False


def test_computer_use_first_nav_and_followup_envelope_bcff5702() -> None:
    row = _load("gravitre-computer-use-browser-live.json")
    assert str(row.get("health_sha") or "").startswith("bcff5702")
    first = row["first_turn"]
    assert int(first["first_useful_text_ms"]) <= _FIRST_USEFUL_MAX_MS
    assert int(first["completion_ms"]) <= _COMPLETION_MAX_MS
    assert first.get("used_httpx_claim") is False
    follow = row["follow_up"]
    assert int(follow["first_useful_text_ms"]) <= _FOLLOWUP_FIRST_USEFUL_MAX_MS
    residual = row["residual_gap_closed"]
    assert residual.get("obs_count_after_followup") == 1
    assert residual.get("meets_5s_8s_band") is True
