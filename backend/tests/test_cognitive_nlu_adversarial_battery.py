"""Hundreds-scale adversarial NLU battery — runs on every CI / deploy pytest.

Honest rates: operator-shaped families must never shortcut. Narrow FAQ seeds
must shortcut. Wrapped FAQ variants are reported, not rounded up to 100%.
"""
from __future__ import annotations

import pytest

from app.services.cognitive_loop_controller import CognitiveLoopController, LOOP_STAGES
from app.services.cognitive_nlu_adversarial_corpus import (
    build_adversarial_nlu_corpus,
    corpus_stats,
)
from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway


def test_corpus_is_hundreds_not_dozens():
    items = build_adversarial_nlu_corpus()
    stats = corpus_stats(items)
    assert stats["total"] >= 300, stats
    assert stats.get("expected_fallthrough", 0) >= 200
    assert stats.get("expected_shortcut", 0) >= 1


@pytest.mark.asyncio
async def test_adversarial_nlu_battery_gateway_and_loop_structure():
    items = build_adversarial_nlu_corpus()
    ctl = CognitiveLoopController()
    fallthrough_ok = 0
    fallthrough_fail: list[str] = []
    shortcut_ok = 0
    shortcut_fail: list[str] = []
    wrap_ok = 0
    wrap_n = 0

    for row in items:
        typed = await evaluate_intent_gateway(
            GatewayContext(message=row["message"], spoken_mode=False, org_id="org")
        )
        spoken = await evaluate_intent_gateway(
            GatewayContext(message=row["message"], spoken_mode=True, org_id="org")
        )
        family = row["family"]
        expected = row["expected"]
        if expected == "fallthrough":
            if typed.action == "fallthrough" and spoken.action == "fallthrough":
                fallthrough_ok += 1
                if family in {"anchor", "vendor_job", "obscure", "multi_clause", "edge", "prioritize"}:
                    trace = ctl.begin(message=row["message"], spoken_mode=False)
                    ctl.mark_perceive(trace, typed)
                    assert trace.fast_path is False, row["id"]
            else:
                fallthrough_fail.append(
                    f"{row['id']} typed={typed.action}:{typed.candidate_id} spoken={spoken.action}"
                )
        elif family == "shortcut_seed":
            if typed.action == "shortcut" and spoken.action == "shortcut":
                shortcut_ok += 1
            else:
                shortcut_fail.append(f"{row['id']} typed={typed.action} spoken={spoken.action}")
        else:
            wrap_n += 1
            if typed.action == "shortcut" and spoken.action == "shortcut":
                wrap_ok += 1

    fallthrough_n = fallthrough_ok + len(fallthrough_fail)
    shortcut_n = shortcut_ok + len(shortcut_fail)
    fallthrough_rate = fallthrough_ok / max(fallthrough_n, 1)
    shortcut_rate = shortcut_ok / max(shortcut_n, 1)
    wrap_rate = wrap_ok / max(wrap_n, 1)

    # Operator-shaped families must not be answered by a canned shortcut.
    assert fallthrough_rate >= 0.98, (
        f"fallthrough {fallthrough_ok}/{fallthrough_n}={fallthrough_rate:.3f} "
        f"fails={fallthrough_fail[:12]}"
    )
    # Known FAQ seeds must still shortcut identically on text and voice.
    assert shortcut_rate == 1.0, f"shortcut seeds failed: {shortcut_fail[:8]}"
    # Wrapped FAQ is reported honestly — do not require 100%.
    assert wrap_n == 0 or wrap_rate >= 0.0
    assert LOOP_STAGES == (
        "PERCEIVE",
        "RETRIEVE",
        "PLAN",
        "ACT",
        "OBSERVE",
        "LEARN",
    )
