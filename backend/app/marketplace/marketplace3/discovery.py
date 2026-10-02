"""Structured Marketplace 3.0 metadata for Ask Gravitre recommendation.

This is not a separate recommendation engine. It exposes pack contracts in a
shape existing Gravitre AI can reason over.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.marketplace3.connector_groups import evaluate_connector_or_groups
from app.marketplace.schemas import OutcomePackAssetConfig


def outcome_pack_discovery_metadata(
    config: OutcomePackAssetConfig,
    *,
    connected_vendors: set[str] | None = None,
) -> dict[str, Any]:
    connected = connected_vendors or set()
    required_types = sorted(
        {
            profile.provider
            for profile in config.runtime_profiles
        }
    )
    supported = sorted(
        {
            member
            for group in config.connector_alternatives
            for member in group
            if str(member).strip()
        }
        | set(required_types)
    )
    readiness = evaluate_connector_or_groups(
        connected=connected,
        required_connectors=[
            {"connectorType": provider, "required": True}
            for provider in required_types
        ],
        alternatives=config.connector_alternatives,
    )
    play_ready = 0
    play_rows: list[dict[str, Any]] = []
    for play in config.plays:
        vendors = sorted(
            {
                str((step.get("config") or {}).get("connector") or "").strip()
                for step in play.workflow_steps
                if isinstance(step, dict) and step.get("type") == "invoke_tool"
            }
            - {""}
        )
        supported_by_connection = all(vendor in connected for vendor in vendors)
        if supported_by_connection:
            play_ready += 1
        play_rows.append(
            {
                "key": play.key,
                "name": play.name,
                "outcomeEvents": list(play.outcome_events),
                "kpiKeys": list(play.kpi_keys),
                "systems": vendors,
                "missingSystems": sorted(set(vendors) - connected),
                "runtimeInputs": list(play.runtime_inputs),
                "supportedByConnectedSystems": supported_by_connection,
            }
        )
    return {
        "jobToBeDone": config.outcome_contract.problem,
        "targetOutcome": config.outcome_contract.target_outcome,
        "playCount": len(config.plays),
        "supportedPlayCount": play_ready,
        "kpiKeys": [kpi.key for kpi in config.outcome_contract.kpis],
        "requiredSystems": required_types,
        "supportedSystems": supported,
        "connectorGroups": readiness["groups"],
        "plays": play_rows,
    }
