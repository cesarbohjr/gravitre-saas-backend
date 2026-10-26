"""Goal templates offered on the Goals page: the outcome, its metric and how often it runs.

``frequency`` uses the same values a goal stores (once, daily, weekly, monthly, ongoing),
so a goal created from a template keeps the template's cadence.
"""
from __future__ import annotations

from typing import Any

GOAL_FREQUENCIES = ("once", "daily", "weekly", "monthly", "ongoing")

GOAL_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "id": "marketing-signups",
        "department": "marketing",
        "objective": "Grow qualified signups from content",
        "metric": "Qualified signups from content",
        "frequency": "weekly",
        "illustration": "goal-template-marketing",
    },
    {
        "id": "finance-overdue",
        "department": "finance",
        "objective": "Reduce overdue invoices",
        "metric": "Overdue invoices",
        "frequency": "daily",
        "illustration": "goal-template-finance",
    },
    {
        "id": "support-response",
        "department": "support",
        "objective": "Answer every ticket within one business day",
        "metric": "Tickets answered within one business day",
        "frequency": "ongoing",
        "illustration": "goal-template-support",
    },
)


def list_goal_templates() -> list[dict[str, Any]]:
    return [dict(t) for t in GOAL_TEMPLATES]
