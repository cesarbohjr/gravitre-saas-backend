"""Few-shot prompts injected into live system prompts must not overlap the eval batteries.

If a live battery asks the same question the system prompt already answers, a
passing battery proves recall of the few-shot, not conversational ability. This
guards both few-shot sources injected into production prompts:
``MODULE_D_FEW_SHOT_EXCHANGES`` and the per-department expert dialogue library.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.services.conversation_parity_benchmark import SCENARIOS
from app.services.expert_dialogue_library import _EXPERT_DIALOGUES
from app.services.module_d_unified_voice_spec import MODULE_D_FEW_SHOT_EXCHANGES

REPO_ROOT = Path(__file__).resolve().parents[3]
SHINGLE_WORDS = 5
# Phatic turns ("hello there", "appreciate it") are not task prompts and appear
# in every conversation; overlap on them says nothing about answer leakage.
MIN_PROMPT_WORDS = 4


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip() + " "


def _shingles(text: str) -> set[str]:
    words = _norm(text).split()
    return {" ".join(words[i : i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def _battery_corpus() -> dict[str, str]:
    corpus = {
        str(path.relative_to(REPO_ROOT)): _norm(path.read_text(encoding="utf-8"))
        for path in sorted((REPO_ROOT / "scripts").glob("verify-*live*.py"))
    }
    corpus["conversation_parity_benchmark.SCENARIOS"] = _norm(
        "\n".join(turn for scenario in SCENARIOS for turn in scenario.turns)
    )
    return corpus


def _few_shot_prompts() -> list[tuple[str, str]]:
    prompts = [("module_d", user) for user, _ in MODULE_D_FEW_SHOT_EXCHANGES]
    for dept, rows in _EXPERT_DIALOGUES.items():
        prompts.extend((f"expert:{dept}", user) for user, _, _ in rows)
    return [(src, text) for src, text in prompts if len(_norm(text).split()) >= MIN_PROMPT_WORDS]


def test_corpus_is_present() -> None:
    # A missing scripts/ directory would make every overlap check pass vacuously.
    corpus = _battery_corpus()
    assert "scripts/verify-expert-dialogue-live.py" in corpus
    assert "scripts/verify-conversational-behavior-all-surfaces-live.py" in corpus


@pytest.mark.parametrize(("source", "prompt"), _few_shot_prompts())
def test_few_shot_prompt_does_not_overlap_live_batteries(source: str, prompt: str) -> None:
    corpus = _battery_corpus()
    shingles = _shingles(prompt)
    hits = sorted(
        f"{path}: '{shingle}'"
        for path, text in corpus.items()
        for shingle in shingles
        if f" {shingle} " in text
    )
    assert not hits, f"{source} few-shot {prompt!r} overlaps eval batteries: {hits[:5]}"


def test_detector_catches_a_planted_overlap() -> None:
    planted = "Should we score candidates with AI on scraped resumes from job boards?"
    corpus = _battery_corpus()
    assert any(f" {s} " in corpus["scripts/verify-expert-dialogue-live.py"] for s in _shingles(planted))
