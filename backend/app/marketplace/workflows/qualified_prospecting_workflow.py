"""Canonical-workflow step definitions for a guarded Prospecting Play.

These are invoke_tool actions, not a second runtime. Write steps deliberately
omitted until policy-approved CRM staging is implemented and exercised.
"""
from __future__ import annotations
from typing import Any

from app.marketplace.workflows.step_builders import invoke_step

PLAY_KEY="qualified-prospecting"
WORKFLOW_SLUG="qualified-prospecting-research-v1"

def build_prospecting_read_workflow_steps() -> list[dict[str,Any]]:
    """Read-only provider execution within the existing canonical workflow builder."""
    return [
        invoke_step(
            "find_decision_makers", "Find prospect decision-makers",
            "apollo.people.search", connector="apollo",
            params={"q_keywords":"managed service provider CEO owner", "per_page":10}
        ),
    ]

def workflow_config() -> dict[str,Any]:
    return {
        "workflow_slug":WORKFLOW_SLUG,
        "play":{"key":PLAY_KEY,"version":"1","execution_authority":"canonical_workflow_runtime"},
        "requires_source_review":True,
        "requires_contact_review":True,
        "crm_writes_enabled":False,
        "outbound_email_enabled":False,
    }
