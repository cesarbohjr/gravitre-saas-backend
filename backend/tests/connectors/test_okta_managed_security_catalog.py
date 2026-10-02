from app.connectors.action_catalog.registry import get_action_spec, get_vendor_spec
from app.services.tool_service import list_registered_actions


def test_okta_security_catalog_is_registered_and_read_only() -> None:
    vendor = get_vendor_spec("okta")
    assert vendor is not None
    actions = {action.id for action in vendor.all_actions()}
    assert {"okta.system_logs.list", "okta.users.get"} <= actions

    for action_id in {"okta.system_logs.list", "okta.users.get"}:
        spec = get_action_spec(action_id)
        assert spec is not None
        assert spec.kind == "read"
        assert spec.requires_approval is False
        assert action_id in set(list_registered_actions())
