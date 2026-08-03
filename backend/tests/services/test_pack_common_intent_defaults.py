"""Part 3 — pack-common intent defaults (MSP / Prospecting approve-first slots)."""
from __future__ import annotations

from app.marketplace.workflows.msp_prospecting_list_workflow import (
    DEFAULT_APOLLO_LIST_NAME,
    DEFAULT_HUBSPOT_LIST_NAME,
)
from app.services.chat_connector_models import ConnectorActionPlan
from app.services.pack_common_intent_defaults import (
    apply_pack_common_defaults,
    pack_common_default_catalog,
)


def _plan(action: str, **args: object) -> ConnectorActionPlan:
    return ConnectorActionPlan(
        tool_name=action.replace(".", "_"),
        invoke_action=action,
        integration=action.split(".", 1)[0],
        kind="write",
        label=action,
        args=dict(args),
        requires_approval=True,
    )


def test_apollo_omit_name_defaults_msp_prospects():
    out = apply_pack_common_defaults(
        _plan("apollo.lists.create", modality="contacts"),
        message="Create a contact list in Apollo",
    )
    assert out.args.get("name") == DEFAULT_APOLLO_LIST_NAME
    assert "name" in out.inferred_fields


def test_apollo_named_list_preserves_explicit():
    out = apply_pack_common_defaults(
        _plan("apollo.lists.create", name="Q3 MSP Targets", modality="contacts"),
        message='Create Apollo list named Q3 MSP Targets',
    )
    assert out.args.get("name") == "Q3 MSP Targets"


def test_hubspot_omit_name_defaults_msps():
    out = apply_pack_common_defaults(
        _plan("hubspot.lists.create"),
        message="Create a HubSpot static list",
    )
    assert out.args.get("name") == DEFAULT_HUBSPOT_LIST_NAME
    assert out.args.get("processing_type") == "MANUAL"
    assert out.args.get("object_type_id") == "0-1"
    assert out.inference_sources.get("name") == "pack_common_default"


def test_hubspot_trailing_msps_name():
    out = apply_pack_common_defaults(
        _plan("hubspot.lists.create"),
        message="Create HubSpot static list MSPs",
    )
    assert out.args.get("name") == "MSPs"


def test_apollo_lists_add_defaults_list_not_entities():
    out = apply_pack_common_defaults(
        _plan("apollo.lists.add"),
        message="Add contacts to MSP Prospects",
    )
    assert out.args.get("list_name") == DEFAULT_APOLLO_LIST_NAME
    assert "entity_ids" not in out.args
    assert "contact_ids" not in out.args


def test_ambiguous_my_list_does_not_invent_target():
    out = apply_pack_common_defaults(
        _plan("apollo.lists.add"),
        message="Enrich my list with Clay",
    )
    assert not out.args.get("list_name")
    assert not out.args.get("label_names")


def test_clay_crm_sync_defaults_crm_not_records():
    out = apply_pack_common_defaults(
        _plan("clay.crm.sync"),
        message="Sync enriched MSP Prospects to HubSpot",
    )
    assert out.args.get("crm") == "hubspot"
    assert "records" not in out.args


def test_catalog_covers_msp_and_prospecting_actions():
    rows = pack_common_default_catalog()
    actions = {r["invoke_action"] for r in rows}
    assert "apollo.lists.create" in actions
    assert "hubspot.lists.create" in actions
    for row in rows:
        assert "msp-intelligence-pack" in row["pack_ids"]
        assert "prospecting-intelligence-pack" in row["pack_ids"]
