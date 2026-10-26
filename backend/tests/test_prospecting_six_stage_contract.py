from app.marketplace.workflows.qualified_prospecting_workflow import (
    STAGE_ORDER, STAGE_ACTIONS, build_six_stage_workflow_steps,
    six_stage_complete,
)

def test_six_stages_ordered_and_unique():
    steps = build_six_stage_workflow_steps()
    assert len(steps) == 6
    assert [step["id"] for step in steps] == [
        "prospecting_" + stage for stage in STAGE_ORDER
    ]
    assert len(set(STAGE_ACTIONS.values())) == 6

def test_review_and_staging_have_explicit_approval_requirements():
    steps = build_six_stage_workflow_steps()
    assert all(step["config"].get("requires_approval") is True for step in steps[-2:])

def test_missing_tool_prevents_activation():
    assert not six_stage_complete({"apollo.people.search"})
    assert six_stage_complete(set(STAGE_ACTIONS.values()))
