"""Named inline progress labels for chat plan-bar (progress UX v1)."""
from __future__ import annotations

from app.services.agent_platform_optimizer import (
    append_named_progress_step,
    build_progress_steps,
    format_live_progress_label,
    progress_steps_from_pending_task,
)


def test_format_live_progress_label_named_tool_and_query():
    label = format_live_progress_label("web_search", {"query": "MSP prospects in Seattle"})
    assert label.startswith("Searching the web:")
    assert "MSP prospects" in label


def test_format_live_progress_label_humanizes_catalog_action():
    label = format_live_progress_label("apollo.lists.create", {})
    assert "apollo.lists.create" not in label.lower()
    assert label  # non-empty plain language


def test_append_named_progress_step_marks_prior_running_complete():
    steps = append_named_progress_step([], "Searching the web")
    assert steps == ["Running: Searching the web"]
    steps = append_named_progress_step(steps, "Create contact list")
    assert steps[0] == "Completed: Searching the web"
    assert steps[1] == "Running: Create contact list"


def test_progress_steps_from_pending_task_uses_step_labels():
    steps = progress_steps_from_pending_task(
        {
            "params": {
                "steps": [
                    {"label": "Create contact list"},
                    {"label": "Search contacts"},
                    {"invoke_action": "hubspot.contacts.create"},
                ]
            }
        }
    )
    assert steps[0].startswith("Step 1/3:")
    assert "Create contact list" in steps[0]
    assert steps[1].startswith("Step 2/3:")
    assert len(steps) == 3


def test_build_progress_steps_context_is_specific():
    steps = build_progress_steps(
        routing_tier="research",
        connector_names=["apollo"],
        phase="context",
    )
    assert any("Classifying request" in s for s in steps)
    assert any("Apollo" in s for s in steps)
