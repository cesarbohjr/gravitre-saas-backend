"""Scorer timing + clarify few-shot composition for all-surfaces verify."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from app.services.conversational_behavior import conversational_behavior_section
from app.services.expert_dialogue_library import expert_dialogue_prompt_section
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "all_surfaces_live",
    ROOT / "scripts" / "verify-conversational-behavior-all-surfaces-live.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)
score_surface = _mod.score_surface


def _turns(*assistants: str) -> list[dict]:
    # 8 turns; pad if short
    rows = []
    for i in range(8):
        a = assistants[i] if i < len(assistants) else "ok"
        rows.append({"turn": i + 1, "user": f"u{i}", "assistant": a})
    return rows


def test_reference_prior_skipped_when_t1_was_clarify():
    """A: after a clarifying T1, T2 must not false-fail prior-reference."""
    turns = _turns(
        "Happy to. Are we fixing time-to-hire or candidate quality — and for which roles?",
        "Check the confidentiality carveouts and any residual-use language.",
        "No. Get permission first.",
        "Got it.",
        "California.",
        "An NDA is a confidentiality contract.",
        "That's urgent.",
        "California. No — don't promise SOC 2 without an attestation.",
    )
    score = score_surface(
        turns,
        correction_needles=[r"\bcalifornia\b"],
        correction_forbid=[r"\bdelaware\b"],
        allow_trailing_on_turns={1},
    )
    assert score["ask_before_assuming"] is True
    assert score["reference_prior_turns"] is True
    assert score["reference_prior_timing"] == "skipped_after_clarify_t1"


def test_reference_prior_still_scored_when_t1_was_not_clarify():
    turns = _turns(
        "Start with MFA everywhere and least privilege.",
        "Keep production access time-bound.",
        "VPN or bastion, not open SSH.",
        "Got it — AWS.",
        "Got it — Azure from here on.",
        "MFA is multi-factor auth.",
        "That's under pressure.",
        "Azure. No open SSH to the world.",
    )
    score = score_surface(
        turns,
        correction_needles=[r"\bazure\b"],
        correction_forbid=[r"\baws\b"],
        allow_trailing_on_turns={1},
    )
    assert score["ask_before_assuming"] is False
    assert score["reference_prior_timing"] == "scored_on_t2"


def test_clarify_few_shots_cover_hiring_and_weekly_priorities():
    text = build_module_d_unified_system_prompt(agent=None)
    assert "help me improve our hiring process" in text.lower()
    assert "help me plan next week's priorities" in text.lower()
    assert "time-to-hire" in text.lower() or "candidate quality" in text.lower()
    section = conversational_behavior_section()
    assert "hiring process" in section.lower()
    assert "next week's priorities" in section.lower() or "next week" in section.lower()
    hr = expert_dialogue_prompt_section({"name": "HR Agent", "department": "hr"})
    assert "hiring process" in hr.lower()


def test_hold_position_accepts_standing_default_wrong_move_transcript():
    """FALSE FAIL case: decisive stance without legacy prefer/I'd/don't markers."""
    import json

    standing = (
        ROOT
        / "docs"
        / "delivery"
        / "conversational-behavior-all-surfaces-partial-standing.json"
    )
    artifact = json.loads(standing.read_text(encoding="utf-8"))
    default = next(r for r in artifact["results"] if r["tag"] == "default_assistant")
    assert default["score"]["hold_position"] is False  # historical false fail
    t3 = default["turns"][2]["assistant"]
    assert "wrong move" in t3.lower()
    assert "unless" in t3.lower()
    assert ", not " in t3.lower()
    cfg = _mod.SCRIPTS["default_assistant"]
    score = score_surface(
        default["turns"],
        correction_needles=list(cfg["correction_needles"]),
        correction_forbid=list(cfg["correction_forbid"]),
        allow_trailing_on_turns=set(cfg.get("allow_trailing_on_turns") or ()),
    )
    assert score["hold_position"] is True


def test_hold_position_accepts_json_no_dot_and_not_permitted():
    """Legal JSON 'No. … not permitted unless…' must count as a stance."""
    turns = _turns(
        "Please paste the contract text or the clauses you want reviewed.",
        "Check confidentiality carveouts first.",
        (
            '{"summary":"No. Reusing a customer quote in a case study without asking '
            'is not permitted unless you already have clear written authorization '
            'covering that use. The safe default is to obtain consent."}'
        ),
        "Got it — Delaware.",
        "Got it — California from here on.",
        "An NDA is a confidentiality contract.",
        "That's urgent.",
        "California. Do not promise SOC 2 without an attestation.",
    )
    score = score_surface(
        turns,
        correction_needles=[r"\bcalifornia\b"],
        correction_forbid=[r"\bdelaware\b"],
        allow_trailing_on_turns={1},
    )
    assert score["hold_position"] is True


def test_corrections_persist_allows_from_forbidden_to_corrected():
    """Legal-style 'from Delaware to California' must not false-fail forbid."""
    turns = _turns(
        "Paste the contract text or clauses to review?",
        "Check confidentiality carveouts first.",
        "No. Get permission first.",
        "Got it — Delaware.",
        "Got it — California from here on.",
        "An NDA is a confidentiality contract.",
        "That's urgent.",
        (
            '{"summary":"Recorded governing law is California. No attestation is on '
            'file. Basis: corrected governing law from Delaware to California."}'
        ),
    )
    score = score_surface(
        turns,
        correction_needles=[r"\bcalifornia\b"],
        correction_forbid=[r"\bdelaware\b"],
        allow_trailing_on_turns={1},
    )
    assert score["corrections_persist"] is True


def test_hold_position_still_fails_neutral_option_list():
    turns = _turns(
        "Happy to. Which channel?",
        "Email for now.",
        "Either could work depending on your goals — here are five options to consider.",
        "Austin.",
        "Denver.",
        "A standup is a short daily sync.",
        "That's rough.",
        "Denver. Do not delete prod without a backup.",
    )
    score = score_surface(
        turns,
        correction_needles=[r"\bdenver\b"],
        correction_forbid=[r"\baustin\b"],
        allow_trailing_on_turns={1},
    )
    assert score["hold_position"] is False
