from unittest.mock import MagicMock, patch

import pytest

from app.marketplace.schemas import OutcomePackAssetConfig
from app.marketplace.service import MarketplaceError, _install_outcome_pack


def _play(key: str, index: int) -> dict:
    return {
        "key": key,
        "name": key.replace("-", " ").title(),
        "description": "A measurable Marketplace 3.0 Play.",
        "trigger": {"type": "manual"},
        "workflow_steps": [
            {
                "id": f"step-{index}",
                "name": "Review",
                "type": "agent",
                "metadata": {"task": "Review evidence and recommend next action."},
            }
        ],
        "outcome_events": [f"{key.replace('-', '_')}_completed"],
        "kpi_keys": ["automation_rate"],
        "verification": {"mode": "source_of_record"},
    }


def _config() -> OutcomePackAssetConfig:
    keys = [
        "client-risk-radar",
        "revenue-leak-hunter",
        "process-drift-detector",
        "knowledge-gap-miner",
        "executive-morning-command-brief",
        "autonomous-exception-manager",
    ]
    return OutcomePackAssetConfig.model_validate(
        {
            "marketplace_version": "3.0",
            "outcome_contract": {
                "problem": "Cross-functional work is fragmented.",
                "target_outcome": "Coordinate measurable work through verified Plays.",
                "success_criteria": ["All required Plays install and emit measurable outcomes."],
                "outcome_events": ["outcome_pack_value_realized"],
                "kpis": [
                    {
                        "key": "automation_rate",
                        "label": "Automation rate",
                        "unit": "percent",
                        "direction": "increase",
                        "source": "play_runs",
                    }
                ],
            },
            "agents": [
                {
                    "seed_label": "agent:ops",
                    "name": "Operations Agent",
                    "purpose": "Coordinate outcome work.",
                }
            ],
            "plays": [_play(key, index) for index, key in enumerate(keys)],
            "knowledge": [{"seed_label": "sop", "title": "Operating SOP"}],
            "dataset": {
                "entities": [
                    {
                        "name": "work_items",
                        "source": "canonical_workflow_runtime",
                        "fields": ["id", "status"],
                    }
                ],
                "metrics": [
                    {
                        "key": "automation_rate",
                        "label": "Automation rate",
                        "formula": "automated / completed",
                        "unit": "percent",
                    }
                ],
            },
            "dashboard": {
                "title": "Outcome Dashboard",
                "metrics": [
                    {
                        "kpi_key": "automation_rate",
                        "label": "Automation rate",
                        "visualization": "trend",
                    }
                ],
            },
            "skills": ["operational-analysis"],
        }
    )


def test_outcome_pack_composes_existing_gravitre_primitives() -> None:
    config = _config()
    client = MagicMock()
    with patch(
        "app.marketplace.service._install_ai_agent",
        return_value={"entityType": "operator", "entityId": "agent-1"},
    ), patch(
        "app.marketplace.service._install_knowledge_pack",
        return_value={"entityType": "knowledge_pack", "entityId": "rag-1", "ragSourceIds": ["rag-1"]},
    ), patch(
        "app.marketplace.service._install_dataset_pack",
        return_value={"entityType": "dataset_pack", "entityId": "dataset-1", "datasetPackId": "dataset-1"},
    ), patch(
        "app.marketplace.service._install_dashboard_pack",
        return_value={"entityType": "dashboard_pack", "entityId": "dashboard-1", "dashboardPackId": "dashboard-1"},
    ), patch(
        "app.marketplace.service._install_play_asset",
        side_effect=[
            {
                "playKey": play.key,
                "playVersion": "1",
                "playInstallationId": f"play-inst-{index}",
                "workflowId": f"workflow-{index}",
                "operatingMode": "OBSERVE",
            }
            for index, play in enumerate(config.plays)
        ],
    ) as play_install:
        result = _install_outcome_pack(
            client,
            "org-1",
            {"id": "11111111-1111-1111-1111-111111111111", "slug": "test-outcome-pack"},
            config,
            actor_id="user-1",
            environment_name="production",
            connector_ids={},
        )

    assert result["entityType"] == "outcome_pack"
    assert result["marketplaceVersion"] == "3.0"
    assert result["executionAuthority"] == "canonical_workflow_runtime"
    assert result["datasetPackId"] == "dataset-1"
    assert result["dashboardPackId"] == "dashboard-1"
    assert len(result["plays"]) == 6
    assert len(result["workflowIds"]) == 6
    assert play_install.call_count == 6


def test_outcome_pack_fails_closed_when_required_play_cannot_install() -> None:
    config = _config()
    client = MagicMock()
    with patch(
        "app.marketplace.service._install_ai_agent",
        return_value={"entityType": "operator", "entityId": "agent-1"},
    ), patch(
        "app.marketplace.service._install_knowledge_pack",
        return_value={"entityType": "knowledge_pack", "entityId": "rag-1", "ragSourceIds": ["rag-1"]},
    ), patch(
        "app.marketplace.service._install_dataset_pack",
        return_value={"entityType": "dataset_pack", "entityId": "dataset-1", "datasetPackId": "dataset-1"},
    ), patch(
        "app.marketplace.service._install_dashboard_pack",
        return_value={"entityType": "dashboard_pack", "entityId": "dashboard-1", "dashboardPackId": "dashboard-1"},
    ), patch(
        "app.marketplace.service._install_play_asset",
        side_effect=RuntimeError("play could not bind"),
    ):
        with pytest.raises(MarketplaceError) as exc:
            _install_outcome_pack(
                client,
                "org-1",
                {"id": "11111111-1111-1111-1111-111111111111", "slug": "test-outcome-pack"},
                config,
                actor_id="user-1",
                environment_name="production",
                connector_ids={},
            )

    assert exc.value.code == "OUTCOME_PACK_COMPONENT_FAILED"
    assert exc.value.details["failures"]
    assert exc.value.details["rolledBack"] is True
