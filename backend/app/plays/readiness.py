"""Resolve Play readiness from canonical capability sources.

No Play-local connector/action/governance catalog is allowed here.
"""
from __future__ import annotations

from typing import Any

from app.capabilities.registry import (
    Readiness,
    action_readiness,
    business_metrics,
    connector_readiness,
    event_taxonomy,
    get_action,
    verification_mechanisms,
)
from app.plays.contracts import PlayDefinition, PlayReadiness


_READINESS_ORDER: dict[Readiness, int] = {
    "AVAILABLE": 0,
    "EXTERNAL_CONNECTION_REQUIRED": 1,
    "PARTIAL": 2,
    "MISSING": 3,
}


def _worst(values: list[Readiness]) -> Readiness:
    if not values:
        return "AVAILABLE"
    return max(values, key=lambda value: _READINESS_ORDER[value])


def _known_signals() -> set[str]:
    taxonomy = event_taxonomy()
    out: set[str] = set()
    for values in taxonomy.values():
        out.update(str(value) for value in values)
    return out


def _metric_keys(client: Any, org_id: str | None) -> set[str]:
    metrics = business_metrics(client, org_id) if client is not None and org_id else business_metrics()
    keys: set[str] = set()
    for bucket in ("defaults", "overrides", "definitions"):
        for row in metrics.get(bucket, []) or []:
            if isinstance(row, dict) and row.get("metric_key"):
                keys.add(str(row["metric_key"]).strip().lower())
    return keys


def resolve_play_readiness(
    definition: PlayDefinition,
    *,
    connected_vendors: set[str] | None,
    client: Any = None,
    org_id: str | None = None,
    policy_authorized_actions: set[str] | None = None,
) -> PlayReadiness:
    """Resolve current Play maturity without executing anything.

    `policy_authorized_actions` must come from a runtime/effective-policy
    evaluation for the relevant agent/context. Absence never means authorized.
    """

    blockers: list[str] = []
    status_values: list[Readiness] = []

    connector_groups: list[dict[str, Any]] = []
    for group in definition.required_connector_groups:
        vendors = tuple(str(v).strip().lower() for v in group if str(v).strip())
        vendor_states = {vendor: connector_readiness(vendor, connected_vendors) for vendor in vendors}
        available = any(state == "AVAILABLE" for state in vendor_states.values())
        if available:
            group_status: Readiness = "AVAILABLE"
        elif any(state == "EXTERNAL_CONNECTION_REQUIRED" for state in vendor_states.values()):
            group_status = "EXTERNAL_CONNECTION_REQUIRED"
        elif any(state == "PARTIAL" for state in vendor_states.values()):
            group_status = "PARTIAL"
        else:
            group_status = "MISSING"
        status_values.append(group_status)
        connector_groups.append(
            {
                "vendors": list(vendors),
                "status": group_status,
                "alternatives": vendor_states,
            }
        )
        if group_status != "AVAILABLE":
            blockers.append(f"connector group {' | '.join(vendors)}: {group_status}")

    action_rows: list[dict[str, Any]] = []
    read_group_states: list[Readiness] = []
    write_group_states: list[Readiness] = []
    available_write_choices: list[tuple[str, ...]] = []

    def _resolve_action_group(group: tuple[str, ...], *, access: str) -> tuple[Readiness, tuple[str, ...]]:
        tools = tuple(str(tool).strip() for tool in group if str(tool).strip())
        states: dict[str, Readiness] = {}
        matching_available: list[str] = []
        for tool in tools:
            cap = get_action(tool)
            state = action_readiness(tool, connected_vendors)
            if cap is None or cap.access != access:
                state = "MISSING"
            states[tool] = state
            action_rows.append(
                {
                    "tool": tool,
                    "group_access": access,
                    "status": state,
                    "access": cap.access if cap else None,
                    "requires_approval": cap.requires_approval if cap else None,
                    "verification_mode": cap.verification_mode if cap else None,
                }
            )
            if state == "AVAILABLE":
                matching_available.append(tool)
        if matching_available:
            group_status: Readiness = "AVAILABLE"
        elif any(state == "EXTERNAL_CONNECTION_REQUIRED" for state in states.values()):
            group_status = "EXTERNAL_CONNECTION_REQUIRED"
        elif any(state == "PARTIAL" for state in states.values()):
            group_status = "PARTIAL"
        else:
            group_status = "MISSING"
        status_values.append(group_status)
        if group_status != "AVAILABLE":
            blockers.append(f"{access} action group {' | '.join(tools)}: {group_status}")
        return group_status, tuple(matching_available)

    for group in definition.required_read_action_groups:
        state, _available = _resolve_action_group(group, access="read")
        read_group_states.append(state)

    for group in definition.write_action_groups:
        state, available = _resolve_action_group(group, access="write")
        write_group_states.append(state)
        available_write_choices.append(available)

    known_signals = _known_signals()
    signal_rows: list[dict[str, Any]] = []
    for signal in definition.required_signals:
        state: Readiness = "AVAILABLE" if signal in known_signals else "MISSING"
        signal_rows.append({"signal": signal, "status": state})
        status_values.append(state)
        if state != "AVAILABLE":
            blockers.append(f"signal {signal}: {state}")

    keys = _metric_keys(client, org_id)
    metric_rows: list[dict[str, Any]] = []
    for metric in definition.outcome_metrics:
        state: Readiness = "AVAILABLE" if metric.strip().lower() in keys else "MISSING"
        metric_rows.append({"metric": metric, "status": state})
        # Missing outcome metrics should not prevent Observe/Recommend, but do
        # prevent claiming a fully measurable business outcome.
        if state != "AVAILABLE":
            blockers.append(f"outcome metric {metric}: {state}")

    verification_catalog = verification_mechanisms()
    verification_rows: list[dict[str, Any]] = []
    for requirement in definition.verification_requirements:
        cap = get_action(requirement.action_tool)
        actual = cap.verification_mode if cap else None
        adequate = bool(actual and actual != "accepted_async")
        verification_rows.append(
            {
                "tool": requirement.action_tool,
                "required": requirement.minimum_mode,
                "actual": actual,
                "source_of_record_required": requirement.business_result_requires_source_of_record,
                "adequate_for_verified_result": adequate,
            }
        )
        if not adequate:
            blockers.append(
                f"verification {requirement.action_tool}: {actual or 'MISSING'}"
            )

    observe_ready = (
        all(row["status"] == "AVAILABLE" for row in connector_groups)
        and all(state == "AVAILABLE" for state in read_group_states)
        and all(row["status"] == "AVAILABLE" for row in signal_rows)
    )
    recommend_ready = observe_ready

    act_with_approval_ready = (
        recommend_ready
        and bool(definition.write_action_groups)
        and all(state == "AVAILABLE" for state in write_group_states)
    )

    authorized = policy_authorized_actions or set()
    act_within_policy_ready = (
        act_with_approval_ready
        and bool(available_write_choices)
        and all(any(tool in authorized for tool in choices) for choices in available_write_choices)
    )

    dependency_status = _worst(status_values)

    return PlayReadiness(
        play_key=definition.key,
        dependency_status=dependency_status,
        connector_groups=tuple(connector_groups),
        actions=tuple(action_rows),
        signals=tuple(signal_rows),
        metrics=tuple(metric_rows),
        verification=tuple(verification_rows),
        observe_ready=observe_ready,
        recommend_ready=recommend_ready,
        act_with_approval_ready=act_with_approval_ready,
        act_within_policy_ready=act_within_policy_ready,
        blockers=tuple(blockers),
    )
