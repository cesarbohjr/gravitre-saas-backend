"""When Gravitre may ask the user for connector/resource detail."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ClarificationReason = Literal[
    "resolved",
    "auto_selected_single",
    "ambiguous_multiple",
    "not_connected",
    "not_authorized",
    "missing_resource",
]


@dataclass(frozen=True)
class ClarificationDecision:
    should_ask: bool
    reason: ClarificationReason
    message: str | None = None


def decide_resource_clarification(
    *,
    candidate_count: int,
    resolved_display_name: str | None = None,
    candidate_labels: list[str] | None = None,
    resource_label: str = "property",
) -> ClarificationDecision:
    """ASK ONLY WHEN AMBIGUITY CHANGES THE RESULT OR SAFETY."""
    if candidate_count <= 0:
        return ClarificationDecision(
            should_ask=True,
            reason="missing_resource",
            message=f"I couldn't find a linked {resource_label} for that connector yet.",
        )
    if candidate_count == 1:
        return ClarificationDecision(
            should_ask=False,
            reason="auto_selected_single",
        )
    labels = [label.strip() for label in (candidate_labels or []) if label and label.strip()]
    if not labels:
        return ClarificationDecision(
            should_ask=True,
            reason="ambiguous_multiple",
            message=(
                f"I found {candidate_count} {resource_label}s. "
                f"Which one should I use?"
            ),
        )
    joined = ", ".join(labels[:-1]) + f", and {labels[-1]}" if len(labels) > 1 else labels[0]
    return ClarificationDecision(
        should_ask=True,
        reason="ambiguous_multiple",
        message=(
            f"I found {candidate_count} Google Analytics properties: {joined}. "
            "Which one should I use?"
        ),
    )


def format_not_connected_message(connector_id: str, *, display_name: str | None = None) -> str:
    label = display_name or connector_id.replace("_", " ").title()
    return (
        f"{label} isn't connected yet. Connect it at /connectors and I can analyze "
        "traffic, sources, pages, and trends from your live data."
    )
