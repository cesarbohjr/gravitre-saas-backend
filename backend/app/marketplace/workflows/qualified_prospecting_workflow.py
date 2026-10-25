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


# Canonical six-stage workflow contract. Stages are deliberately separated
# into pure planning, provider invocation, and human-approval boundaries.
# The installer must bind them to registered, tenant-scoped tools before a run.
STAGE_ORDER = ("discover", "research", "enrich", "verify", "consent_review", "stage")
STAGE_ACTIONS = {
    "discover": "prospecting.companies.discover",
    "research": "prospecting.companies.research",
    "enrich": "apollo.people.search",
    "verify": "prospecting.contacts.verify",
    "consent_review": "prospecting.contacts.review",
    "stage": "prospecting.contacts.stage",
}

def build_six_stage_workflow_steps() -> list[dict[str,Any]]:
    """Build canonical step metadata; no direct CRM writes or email sends.

    Local prospecting actions must be registered before installation. The review
    and stage actions must stop on missing consent, missing source evidence, or
    missing canonical approval.
    """
    steps=[]
    for stage in STAGE_ORDER:
        action=STAGE_ACTIONS[stage]
        vendor=action.split(".",1)[0]
        step=invoke_step(
            f"prospecting_{stage}",
            f"Prospecting: {stage.replace('_',' ').title()}",
            action, connector=vendor,
        )
        step["config"]["requires_previous_stage"] = stage != "discover"
        step["config"]["requires_approval"] = stage in {"consent_review","stage"}
        steps.append(step)
    return steps

def six_stage_complete(registered_actions: set[str]) -> bool:
    """Advertise ready only when every stage has a callable registered action."""
    return all(action in registered_actions for action in STAGE_ACTIONS.values())
