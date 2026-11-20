"""Offline A/B/C prompt-composition controls for authored-dialogue evaluation.

This is NOT a generated-response or physical-voice benchmark. It ensures the
three variants can be isolated without changing the model, tenant, or tools.
Run: pytest backend/tests/services/test_authored_dialogue_ablation.py -q
"""
from __future__ import annotations

import pytest

from app.services import expert_dialogue_library as library
from app.services import module_d_unified_voice_spec as module_d

AGENT = {"id": "ablation-agent", "name": "Sales Agent", "department": "sales"}
EXPRESSIVE_EXCHANGES = (
    ("I'm having a rough day. Can we talk?", "Of course. What's been weighing on you?"),
    ("Actually, I meant next Thursday.", "Next Thursday, got it. I'll use that date instead."),
    ("Can you explain that without the jargon?", "Sure. Here's the simpler version."),
)


def build_variant(monkeypatch: pytest.MonkeyPatch, variant: str, *, spoken: bool) -> str:
    with monkeypatch.context() as patch:
        if variant == "current":
            include_general = True
        elif variant == "none":
            include_general = False
            patch.setattr(library, "expert_dialogue_prompt_section", lambda *a, **kw: "")
        elif variant == "expressive":
            include_general = True
            patch.setattr(module_d, "MODULE_D_FEW_SHOT_EXCHANGES", EXPRESSIVE_EXCHANGES)
            patch.setattr(library, "expert_dialogue_prompt_section", lambda *a, **kw: "")
        else:
            raise ValueError(variant)
        return module_d.build_module_d_unified_system_prompt(
            agent=AGENT, spoken_mode=spoken, include_few_shots=include_general
        )


@pytest.mark.parametrize("spoken", [False, True])
def test_three_variants_are_isolated(monkeypatch: pytest.MonkeyPatch, spoken: bool) -> None:
    current = build_variant(monkeypatch, "current", spoken=spoken)
    none = build_variant(monkeypatch, "none", spoken=spoken)
    expressive = build_variant(monkeypatch, "expressive", spoken=spoken)
    assert "Expert dialogue examples (sales)" in current
    assert "Expert dialogue examples (sales)" not in none
    assert "Expert dialogue examples (sales)" not in expressive
    assert "I'm having a rough day" in expressive
    assert "I'm having a rough day" not in current
    assert "I'm having a rough day" not in none
    assert "## Few-shot demonstrations" not in none
    assert "## Few-shot demonstrations" in current
    assert "## Few-shot demonstrations" in expressive
    assert len({current, none, expressive}) == 3


def test_spoken_latency_shortcut_retains_expert_examples() -> None:
    prompt = module_d.build_module_d_unified_system_prompt(
        agent=AGENT, spoken_mode=True, include_few_shots=False
    )
    assert "Expert dialogue examples (sales)" in prompt
    assert "## Few-shot demonstrations" not in prompt
