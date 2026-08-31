"""Conflicting sources: resolve from real signals, or say they conflict.

The resolution ladder is deliberately ordered strongest-signal-first, and the
bottom rung is "unresolved". A resolver that always produced a winner would be
the original bug wearing a new label — silently picking, then presenting the
pick at full confidence.
"""
from __future__ import annotations

from app.services.evidence_contradiction_service import (
    Contradiction,
    format_contradiction_section,
    resolve_contradiction,
)


def _claim(index: int, **fields):
    row = {
        "index": index,
        "claim": fields.pop("claim", f"claim {index}"),
        "kind": fields.pop("kind", "knowledge_pack"),
        "source": fields.pop("source", f"source-{index}"),
        "authority_score": fields.pop("authority_score", None),
        "as_of": fields.pop("as_of", None),
        "superseded": fields.pop("superseded", False),
    }
    row.update(fields)
    return row


def test_supersession_beats_everything_else() -> None:
    """A document the corpus marks superseded loses even with higher authority."""
    con = resolve_contradiction(
        Contradiction(
            subject="notice period",
            claims=[
                _claim(0, superseded=True, authority_score=95, as_of="2030-01-01"),
                _claim(1, superseded=False, authority_score=60, as_of="2019-01-01"),
            ],
        )
    )
    assert con.resolution == "resolved_supersession"
    assert con.winner_index == 1
    assert "superseded" in con.rationale


def test_freshness_resolves_when_every_claim_is_dated() -> None:
    con = resolve_contradiction(
        Contradiction(
            subject="filing deadline",
            claims=[
                _claim(0, as_of="2021-03-01"),
                _claim(1, as_of="2026-02-01"),
            ],
        )
    )
    assert con.resolution == "resolved_freshness"
    assert con.winner_index == 1
    assert "2026-02-01" in con.rationale


def test_freshness_is_not_used_when_a_claim_has_no_date() -> None:
    """Half-dated evidence cannot establish which statement is current."""
    con = resolve_contradiction(
        Contradiction(
            subject="filing deadline",
            claims=[_claim(0, as_of="2026-02-01"), _claim(1, as_of=None)],
        )
    )
    assert con.resolution == "unresolved"


def test_authority_resolves_only_on_a_decisive_gap() -> None:
    decisive = resolve_contradiction(
        Contradiction(
            subject="penalty cap",
            claims=[_claim(0, authority_score=95), _claim(1, authority_score=55)],
        )
    )
    assert decisive.resolution == "resolved_authority"
    assert decisive.winner_index == 0

    marginal = resolve_contradiction(
        Contradiction(
            subject="penalty cap",
            claims=[_claim(0, authority_score=71), _claim(1, authority_score=68)],
        )
    )
    # A 3-point spread is noise, not authority. Refusing to resolve here is the
    # point: a near-tie must not be dressed up as a decision.
    assert marginal.resolution == "unresolved"


def test_org_record_wins_on_a_question_about_the_org() -> None:
    con = resolve_contradiction(
        Contradiction(
            subject="PTO accrual",
            claims=[
                _claim(0, kind="knowledge", source="employee-handbook.pdf"),
                _claim(1, kind="knowledge_pack", source="general HR guidance"),
            ],
        ),
        query="How much PTO do our employees accrue?",
    )
    assert con.resolution == "resolved_org_precedence"
    assert con.winner_index == 0


def test_org_precedence_does_not_apply_to_a_general_question() -> None:
    con = resolve_contradiction(
        Contradiction(
            subject="statutory minimum",
            claims=[
                _claim(0, kind="knowledge", source="some-internal-note.pdf"),
                _claim(1, kind="knowledge_pack", source="statute"),
            ],
        ),
        query="What is the statutory minimum vacation entitlement?",
    )
    # An internal note does not override a statute just because it is internal.
    assert con.resolution == "unresolved"


def test_unresolved_conflict_is_surfaced_with_both_claims() -> None:
    section = format_contradiction_section(
        [
            resolve_contradiction(
                Contradiction(
                    subject="renewal date",
                    claims=[
                        _claim(0, source="CRM export", claim="renews 2026-09-01"),
                        _claim(1, source="signed contract", claim="renews 2026-11-15"),
                    ],
                )
            )
        ]
    )
    assert "UNRESOLVED" in section
    assert "renews 2026-09-01" in section
    assert "renews 2026-11-15" in section
    assert "Do not silently pick one" in section


def test_resolved_conflict_tells_the_model_which_source_won_and_why() -> None:
    section = format_contradiction_section(
        [
            resolve_contradiction(
                Contradiction(
                    subject="notice period",
                    claims=[
                        _claim(0, source="2019 guidance", as_of="2019-01-01"),
                        _claim(1, source="2026 amendment", as_of="2026-01-01"),
                    ],
                )
            )
        ]
    )
    assert "RESOLVED" in section
    assert "2026 amendment" in section
    assert "Do not repeat the" in section


def test_single_claim_is_not_a_conflict() -> None:
    con = resolve_contradiction(Contradiction(subject="x", claims=[_claim(0)]))
    assert con.resolution == "not_a_conflict"


def test_no_conflicts_produces_no_prompt_section() -> None:
    assert format_contradiction_section([]) == ""
