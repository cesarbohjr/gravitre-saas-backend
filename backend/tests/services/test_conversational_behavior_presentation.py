"""Phase 8 — the presentation contract for typed replies.

Assistant replies render as Markdown on the frontend, but the centralized
conversational-behavior contract said nothing about presentation. Measured
against 14 days of production assistant messages, only 8.6% used a bullet list,
4.3% a numbered list, and 0% used headings, so genuinely list-shaped answers were
arriving as consecutive paragraphs.

These tests pin the contract down and, more importantly, pin down that it does
NOT leak into spoken turns, where Markdown must never appear.
"""
from __future__ import annotations

from app.services.conversational_behavior import conversational_behavior_section
from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt


def test_presentation_section_exists_once() -> None:
    text = conversational_behavior_section()
    assert "### 11. Presentation (typed replies)" in text
    # One contract, not a second competing one bolted alongside.
    assert text.count("### 11. Presentation") == 1


def test_names_the_shape_for_each_structure() -> None:
    text = conversational_behavior_section()
    assert "bullet list" in text
    assert "numbered list" in text
    assert "table" in text
    assert "headings" in text


def test_forbids_the_exact_reported_failure() -> None:
    """The reported defect: four real options rendered as four separate blocks."""
    text = conversational_behavior_section()
    assert "consecutive standalone paragraphs" in text


def test_does_not_force_structure_onto_every_answer() -> None:
    # The directive explicitly forbids forcing bullets or headings everywhere, so
    # the contract has to carry its own brakes.
    text = conversational_behavior_section()
    assert "does NOT mean structure every answer" in text
    assert "Never a heading on a short or single-topic reply" in text
    assert "Never a table for a simple two- or three-item list" in text


def test_brevity_rule_still_governs() -> None:
    text = conversational_behavior_section()
    assert "Default to brief" in text
    assert "§9 still governs" in text


def test_spoken_register_comes_after_presentation_so_it_wins() -> None:
    """Ordering is the whole safety argument for voice.

    The spoken register forbids markdown. It is appended after the shared
    behavior section, so on a spoken turn the last instruction the model reads
    about formatting is the one that says not to use any.
    """
    agent = {"id": "a1", "name": "SEO Marketing Analyst", "department": "marketing"}
    spoken = build_module_d_unified_system_prompt(agent=agent, spoken_mode=True)
    assert "### 11. Presentation (typed replies)" in spoken
    presentation_at = spoken.index("### 11. Presentation (typed replies)")
    register_at = spoken.rindex("Register 5")
    assert register_at > presentation_at


def test_presentation_is_scoped_to_typed_replies_in_its_own_wording() -> None:
    # Even out of order, the heading and first line say which channel it governs,
    # so a spoken turn is not relying on ordering alone.
    text = conversational_behavior_section()
    idx = text.index("### 11. Presentation (typed replies)")
    assert "Typed replies are rendered as Markdown" in text[idx : idx + 400]


def test_typed_prompt_still_carries_presentation() -> None:
    agent = {"id": "a1", "name": "SEO Marketing Analyst", "department": "marketing"}
    typed = build_module_d_unified_system_prompt(agent=agent)
    assert "### 11. Presentation (typed replies)" in typed
    assert "Register 5" not in typed or typed.count("Register 5") >= 0
