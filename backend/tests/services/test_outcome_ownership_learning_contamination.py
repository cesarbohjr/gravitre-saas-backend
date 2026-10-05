from app.services.cognitive_outcome_loop import bias_notes_from_event_rows


def test_execution_success_does_not_create_positive_plan_bias() -> None:
    rows = [
        {"outcome_event": "workflow_executed", "entity_id": "wf-1"},
        {"outcome_event": "connector_action_executed", "entity_id": "hubspot"},
        {"outcome_event": "recommendation_created", "entity_id": "rec-1"},
    ]
    result = bias_notes_from_event_rows(rows)
    assert result == {"bias_notes": [], "weight_delta": 0.0}


def test_measured_business_outcome_can_create_positive_bias() -> None:
    rows = [{"outcome_event": "business_metric_improved", "entity_id": "pipeline"}]
    result = bias_notes_from_event_rows(rows)
    assert result["weight_delta"] > 0
    assert result["bias_notes"]


def test_approval_is_not_execution_success() -> None:
    rows = [{"outcome_event": "approval_granted", "entity_id": "write-1"}]
    result = bias_notes_from_event_rows(rows)
    # Approval is a decision signal, not proof the action happened. It may be
    # recalled as a decision but must not be promoted as a successful outcome.
    assert result["weight_delta"] > 0
    assert all("business_outcomes" not in note for note in result["bias_notes"])
