from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.connectors.action_catalog.action_parameters import resolve_action_schema
from app.connectors.action_catalog.registry import get_action_spec
from app.marketplace.marketplace3.department_depth import DEPARTMENT_ENTITIES
from app.marketplace.marketplace3.department_portfolio import (
    build_department_outcome_pack_config,
    department_portfolio_marketplace3_assets,
)
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.certification_runner import fixture_checks
from app.marketplace.marketplace3.discovery import outcome_pack_discovery_metadata
from app.marketplace.schemas import OutcomePackAssetConfig, WorkflowAssetConfig
from app.marketplace.service import _install_play_asset, _install_workflow_entity
from app.plays.catalog import PLATFORM_PLAY_TEMPLATES, get_platform_play
from app.workflows.binding_validation import assert_bindings_valid
from app.workflows.constants import SCHEMA_VERSION
from app.workflows.schema import WorkflowValidationError


@pytest.mark.parametrize("slug", sorted(DEPARTMENT_ENTITIES))
def test_complete_evidence_is_required_by_canonical_readiness_and_runtime(slug: str) -> None:
    config = OutcomePackAssetConfig.model_validate(build_department_outcome_pack_config(slug))
    for play in config.plays:
        actions = {
            step["config"]["action"] for step in play.workflow_steps
            if step["type"] == "invoke_tool"
        }
        assert len(actions) >= 2
        canonical = get_platform_play(play.key)
        assert canonical is not None
        assert set(canonical.required_read_action_groups) == {(action,) for action in actions}
        for action in actions:
            spec = get_action_spec(action)
            assert spec is not None
            assert spec.kind == "read"
        assert_bindings_valid(
            {"schema_version": SCHEMA_VERSION, "steps": play.workflow_steps},
            declared_parameters=set(play.runtime_inputs),
        )
        for step in play.workflow_steps:
            if step["type"] != "invoke_tool":
                continue
            action = step["config"]["action"]
            spec = get_action_spec(action)
            schema = resolve_action_schema(
                action, kind=spec.kind, suffix=action.split(".", 1)[1],
                explicit_schema=spec.input_schema,
            )
            required = set(schema.get("required", []))
            assert required <= set(step["config"].get("param_sources", {})), action
        if play.runtime_inputs:
            assert play.trigger["type"] == "manual"


@pytest.mark.parametrize("slug", sorted(DEPARTMENT_ENTITIES))
def test_enriched_bundle_keeps_catalog_components_and_certification_consistent(slug: str) -> None:
    assets = department_portfolio_marketplace3_assets()
    by_slug = {asset.slug: asset for asset in assets}
    outcome = by_slug[slug]
    config = OutcomePackAssetConfig.model_validate(outcome.config)
    assert len(config.plays) == 8
    assert len(config.knowledge) == 4
    assert "department_records" not in {entity.name for entity in config.dataset.entities}
    assert by_slug[f"{slug}-dataset"].config == config.dataset.model_dump(mode="json")
    assert by_slug[f"{slug}-dashboard"].config == config.dashboard.model_dump(mode="json")
    for play in config.plays:
        child = by_slug[f"{slug}-play-{play.key}"]
        assert child.config == play.model_dump(mode="json")
    for entity in config.dataset.entities:
        if entity.name != "verified_outcomes":
            assert {entity.primary_key, "source_record", "observed_at"} <= set(entity.fields)
    assert all(check.passed for check in fixture_checks(config))
    report = certify_outcome_pack(config)
    assert report.level == "governed"
    assert report.publish_ready is False
    assert all(by_slug[child].status == "draft" for child in outcome.pack_children)
    assert all(by_slug[child].visibility == "internal" for child in outcome.pack_children)


def test_revenue_record_specific_plays_require_a_real_deal_id() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_department_outcome_pack_config("revenue-operations-3")
    )
    for play in config.plays:
        if play.key not in {"meeting-prep-brief", "post-meeting-follow-up-review"}:
            continue
        assert play.runtime_inputs == ["deal_id"]
        assert play.workflow_steps[0]["config"]["param_sources"] == {"deal_id": "$deal_id"}
        assert "CRM deal reads alone do not prove attendance" in play.workflow_steps[-1]["metadata"]["task"]


def test_optional_providers_do_not_become_runtime_equivalent() -> None:
    raw = build_department_outcome_pack_config("revenue-operations-3")
    assert raw["connector_alternatives"][0] == ["hubspot"]
    assert {profile["provider"] for profile in raw["runtime_profiles"]} == {"hubspot"}
    assert "salesforce" in raw["connector_alternatives"][1]


def test_multisystem_plays_are_not_supported_when_only_one_source_is_connected() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_department_outcome_pack_config("customer-success-support-3")
    )
    partial = outcome_pack_discovery_metadata(config, connected_vendors={"hubspot"})
    assert partial["supportedPlayCount"] == 0
    assert all(play["missingSystems"] == ["zendesk"] for play in partial["plays"])
    complete = outcome_pack_discovery_metadata(config, connected_vendors={"hubspot", "zendesk"})
    assert complete["supportedPlayCount"] == 8


def test_signature_play_cannot_shadow_department_evidence_requirements() -> None:
    keys = [play.key for play in PLATFORM_PLAY_TEMPLATES]
    assert len(keys) == len(set(keys))
    play = get_platform_play("revenue-leak-hunter")
    assert play.required_connector_groups == (("quickbooks",), ("stripe",))
    assert len(play.required_read_action_groups) == 3


def test_record_id_declaration_survives_real_play_workflow_installation() -> None:
    config = OutcomePackAssetConfig.model_validate(
        build_department_outcome_pack_config("revenue-operations-3")
    )
    play = next(play for play in config.plays if play.key == "meeting-prep-brief")
    client = MagicMock()
    seed = play.workflow_steps[-1]["metadata"]["agent_seed"]
    with patch("app.marketplace.pack_prewiring.materialize_pack_canvas_graph"), patch(
        "app.marketplace.service.ensure_active_workflow_version"
    ), patch("app.plays.workflow_bindings.bind_play_to_workflow", return_value={"id": "binding-1"}):
        result = _install_play_asset(
            client, "org-1", {"id": "11111111-1111-1111-1111-111111111111", "slug": "meeting-prep"},
            play, actor_id="user-1", environment_name="production",
            connector_ids={"hubspot": "connector-1"}, agent_ids={seed: "agent-1"},
        )
    assert result["operatingMode"] == "OBSERVE"
    calls = client.table.call_args_list
    assert any(call.args[0] == "workflow_defs" for call in calls)
    payloads = [call.args[0] for call in client.table.return_value.upsert.call_args_list]
    workflows = [payload for payload in payloads if isinstance(payload, dict) and "definition" in payload]
    assert workflows[0]["config"]["runtimeInputs"] == ["deal_id"]
    installed = next(payload for payload in payloads if isinstance(payload, dict) and "play_key" in payload)
    assert installed["configuration"]["runtimeInputs"] == ["deal_id"]


def test_undeclared_runtime_alias_cannot_install_a_workflow() -> None:
    raw = build_department_outcome_pack_config("revenue-operations-3")
    play = next(play for play in raw["plays"] if play["key"] == "meeting-prep-brief")
    seed = play["workflow_steps"][-1]["metadata"]["agent_seed"]
    client = MagicMock()
    with pytest.raises(WorkflowValidationError):
        _install_workflow_entity(
            client, "org-1", {"id": "11111111-1111-1111-1111-111111111111"},
            WorkflowAssetConfig(name=play["name"], steps=play["workflow_steps"]),
            actor_id="user-1", environment_name="production",
            connector_ids={"hubspot": "connector-1"}, agent_ids={seed: "agent-1"},
        )
    client.table.assert_not_called()
