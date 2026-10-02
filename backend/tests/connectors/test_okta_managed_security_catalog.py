from app.connectors.action_catalog.registry import get_action_spec, get_vendor_spec
from app.services.tool_service import list_registered_actions


OKTA_SECURITY_ACTIONS = {
    "okta.system_logs.list",
    "okta.users.get",
    "okta.groups.list",
    "okta.apps.list",
    "okta.users.factors.list",
}


def test_okta_security_catalog_is_registered_and_read_only() -> None:
    vendor = get_vendor_spec("okta")
    assert vendor is not None
    actions = {action.id for action in vendor.all_actions()}
    assert OKTA_SECURITY_ACTIONS <= actions

    registered = set(list_registered_actions())
    for action_id in OKTA_SECURITY_ACTIONS:
        spec = get_action_spec(action_id)
        assert spec is not None
        assert spec.kind == "read"
        assert spec.requires_approval is False
        assert action_id in registered


def test_okta_security_catalog_has_three_nonempty_tiers() -> None:
    vendor = get_vendor_spec("okta")
    assert vendor is not None
    assert vendor.v1
    assert vendor.v2
    assert vendor.v3
