"""I7 — Build outcome attribution paths from canonical snapshot evidence.

Does not invent missing steps. Unknown steps stay present in the chain with
honest empty evidence so the UI can inspect gaps.
"""
from __future__ import annotations

from typing import Any

from app.schemas.intelligence_projection import (
    IntelligenceSnapshot,
    OutcomeAttributionPath,
    OutcomePathStep,
)

OUTCOME_PATH_STEP_KINDS = (
    "objective",
    "signal",
    "prediction",
    "agent_workflow",
    "action",
    "outcome",
    "business_impact",
    "learning",
)

STEP_TITLES: dict[str, str] = {
    "objective": "Objective",
    "signal": "Signal",
    "prediction": "Prediction / decision",
    "agent_workflow": "Agent / workflow",
    "action": "Action",
    "outcome": "Outcome",
    "business_impact": "Business impact",
    "learning": "Learning",
}

SIGNAL_EVENTS = frozenset({"recommendation_created", "prediction_generated"})
ACTION_EVENTS = frozenset(
    {
        "connector_action_executed",
        "workflow_executed",
        "recommendation_approved",
        "approval_granted",
    }
)
OUTCOME_RESULT_EVENTS = frozenset(
    {
        "business_metric_improved",
        "business_metric_declined",
        "prediction_validated",
        "prediction_missed",
        "crm_won",
        "crm_lost",
        "crm_booked",
        "user_feedback_positive",
        "user_feedback_negative",
    }
)

_MAX_PATHS = 6
_MAX_EVIDENCE = 4


def _humanize(value: str) -> str:
    return " ".join(part for part in value.replace("_", " ").replace("-", " ").split() if part).title()


def _event_name(row: dict[str, Any]) -> str:
    return str(row.get("event") or row.get("outcome_event") or "").strip()


def _dept_of(row: dict[str, Any]) -> str:
    return str(row.get("department") or "").strip().lower()


def _events_for(events: list[dict[str, Any]], dept_id: str) -> list[dict[str, Any]]:
    if not dept_id or dept_id == "org":
        return events
    return [row for row in events if _dept_of(row) == dept_id]


def _first_matching_event(events: list[dict[str, Any]], kinds: frozenset[str]) -> dict[str, Any] | None:
    for row in events:
        if _event_name(row) in kinds:
            return row
    return None


def _evidence_from_event(row: dict[str, Any]) -> list[str]:
    event = _humanize(_event_name(row))
    created = str(row.get("createdAt") or row.get("created_at") or "").strip()
    entity = str(row.get("entityId") or row.get("entity_id") or row.get("agentId") or row.get("agent_id") or "").strip()
    lines = [event] if event else []
    if entity:
        lines.append(f"Linked record {entity[:24]}")
    if created:
        lines.append(created[:19].replace("T", " "))
    return lines[:_MAX_EVIDENCE]


def _unknown_step(kind: str) -> OutcomePathStep:
    return OutcomePathStep(
        kind=kind,  # type: ignore[arg-type]
        title=STEP_TITLES[kind],
        label="Not enough verified data yet",
        present=False,
        evidence=[],
        sourceRecordId=None,
        qualityNote="INSUFFICIENT_EVIDENCE",
    )


def _present_step(
    kind: str,
    *,
    label: str,
    evidence: list[str],
    source_record_id: str | None = None,
) -> OutcomePathStep:
    return OutcomePathStep(
        kind=kind,  # type: ignore[arg-type]
        title=STEP_TITLES[kind],
        label=label,
        present=True,
        evidence=[line for line in evidence if line][:_MAX_EVIDENCE],
        sourceRecordId=source_record_id,
        qualityNote=None,
    )


def _build_path_for_scope(
    snapshot: IntelligenceSnapshot,
    *,
    scope_id: str,
    scope_label: str,
    events: list[dict[str, Any]],
    measured_count: int | None,
) -> OutcomeAttributionPath:
    outcomes = list(snapshot.outcomes or [])
    scoped_events = _events_for(outcomes if outcomes else events, scope_id)

    objective = _present_step(
        "objective",
        label=scope_label,
        evidence=[f"Department scope {scope_id}"] if scope_id != "org" else ["Organization-wide attribution"],
        source_record_id=scope_id,
    )

    signal_event = _first_matching_event(scoped_events, SIGNAL_EVENTS)
    signal_row = None
    for row in snapshot.signals or []:
        if not isinstance(row, dict):
            continue
        dept = str(row.get("department") or row.get("department_id") or "").strip().lower()
        if scope_id != "org" and dept and dept != scope_id:
            continue
        title = str(row.get("title") or "").strip()
        if title:
            signal_row = row
            break
    if signal_row:
        signal = _present_step(
            "signal",
            label=str(signal_row.get("title") or "Business signal")[:160],
            evidence=[str(signal_row.get("summary") or signal_row.get("signal_type") or "")],
            source_record_id=str(signal_row.get("id") or "") or None,
        )
    elif signal_event:
        signal = _present_step(
            "signal",
            label=_humanize(_event_name(signal_event)),
            evidence=_evidence_from_event(signal_event),
            source_record_id=str(signal_event.get("id") or "") or None,
        )
    else:
        signal = _unknown_step("signal")

    prediction_match = None
    for pred in snapshot.predictions:
        dept = str(pred.department or "").strip().lower().replace(" ", "_")
        if scope_id == "org" or not dept or dept == scope_id or scope_id in dept or dept in scope_id:
            prediction_match = pred
            break
    if prediction_match:
        prediction = _present_step(
            "prediction",
            label=prediction_match.businessStatement[:160],
            evidence=list(prediction_match.evidence or [])[:_MAX_EVIDENCE]
            or ([prediction_match.horizon] if prediction_match.horizon else []),
            source_record_id=prediction_match.id,
        )
    else:
        prediction = _unknown_step("prediction")

    agent_match = None
    for agent in snapshot.agents:
        dept = str(agent.department or "").strip().lower().replace(" ", "_")
        if scope_id == "org" or not dept or dept == scope_id:
            agent_match = agent
            break
    agent_event = None
    for row in scoped_events:
        entity_type = str(row.get("entityType") or row.get("entity_type") or "").lower()
        if entity_type in {"agent", "workflow"} or row.get("agentId") or row.get("agent_id"):
            agent_event = row
            break
    if agent_match:
        agent_step = _present_step(
            "agent_workflow",
            label=agent_match.businessLabel or agent_match.name,
            evidence=[
                f"Configured {agent_match.configuredStatus}",
                f"Execution {agent_match.executionStatus}",
            ],
            source_record_id=agent_match.id,
        )
    elif agent_event:
        agent_step = _present_step(
            "agent_workflow",
            label="Recorded agent or workflow activity",
            evidence=_evidence_from_event(agent_event),
            source_record_id=str(agent_event.get("agentId") or agent_event.get("agent_id") or "") or None,
        )
    else:
        agent_step = _unknown_step("agent_workflow")

    action_event = _first_matching_event(scoped_events, ACTION_EVENTS)
    action = (
        _present_step(
            "action",
            label=_humanize(_event_name(action_event)),
            evidence=_evidence_from_event(action_event),
            source_record_id=str(action_event.get("id") or "") or None,
        )
        if action_event
        else _unknown_step("action")
    )

    outcome_event = _first_matching_event(scoped_events, OUTCOME_RESULT_EVENTS)
    if not outcome_event:
        # Fall back to any scoped outcome event so the chain can still cite work.
        outcome_event = scoped_events[0] if scoped_events else None
    outcome = (
        _present_step(
            "outcome",
            label=_humanize(_event_name(outcome_event)),
            evidence=_evidence_from_event(outcome_event),
            source_record_id=str(outcome_event.get("id") or "") or None,
        )
        if outcome_event
        else _unknown_step("outcome")
    )

    if measured_count is not None and measured_count > 0:
        impact = _present_step(
            "business_impact",
            label=f"{measured_count} measured outcome{'s' if measured_count != 1 else ''} in this scope",
            evidence=["Canonical IMPROVES projection — counted outcomes only, not estimated dollars"],
            source_record_id=scope_id,
        )
    else:
        impact = _unknown_step("business_impact")

    learning_match = snapshot.learnings[0] if snapshot.learnings else None
    learning = (
        _present_step(
            "learning",
            label=learning_match.businessStatement[:160],
            evidence=list(learning_match.evidence or [])[:_MAX_EVIDENCE]
            or list(learning_match.learnedFrom or [])[:_MAX_EVIDENCE],
            source_record_id=learning_match.id,
        )
        if learning_match
        else _unknown_step("learning")
    )

    steps = [objective, signal, prediction, agent_step, action, outcome, impact, learning]
    present_count = sum(1 for step in steps if step.present)
    return OutcomeAttributionPath(
        id=f"path:{scope_id}",
        scopeId=scope_id,
        scopeLabel=scope_label,
        steps=steps,
        presentStepCount=present_count,
        complete=present_count == len(OUTCOME_PATH_STEP_KINDS),
    )


def build_outcome_paths(snapshot: IntelligenceSnapshot) -> list[OutcomeAttributionPath]:
    """Compose department (or org) attribution chains from snapshot evidence only."""
    events = list(snapshot.outcomes or [])
    paths: list[OutcomeAttributionPath] = []

    departments = list(snapshot.departments or [])[:_MAX_PATHS]
    if departments:
        for dept in departments:
            dept_id = str(dept.get("id") or "").strip().lower()
            if not dept_id:
                continue
            resolved = dept.get("recentResolved")
            measured = int(resolved) if isinstance(resolved, (int, float)) else None
            paths.append(
                _build_path_for_scope(
                    snapshot,
                    scope_id=dept_id,
                    scope_label=_humanize(dept_id),
                    events=events,
                    measured_count=measured,
                )
            )
    else:
        measured = snapshot.metrics.outcomes.get("measuredOutcomes") if snapshot.metrics else None
        measured_int = int(measured) if isinstance(measured, (int, float)) and measured else None
        paths.append(
            _build_path_for_scope(
                snapshot,
                scope_id="org",
                scope_label="Organization",
                events=events,
                measured_count=measured_int,
            )
        )

    # Drop empty org-only shells with zero evidence except the objective label.
    filtered = [path for path in paths if path.presentStepCount > 1 or path.scopeId == "org"]
    return filtered or paths
