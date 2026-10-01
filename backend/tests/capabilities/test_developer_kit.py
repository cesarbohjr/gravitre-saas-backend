from app.capabilities.developer_kit import developer_kit_contract


def test_developer_kit_never_claims_direct_script_execution() -> None:
    contract = developer_kit_contract()
    assert contract["security"]["scriptsExecuteDirectly"] is False
    assert contract["security"]["privateSigningKeysAccepted"] is False
    assert contract["supportedPortableActivation"]["skill"] == "lazy_context"
    assert contract["supportedPortableActivation"]["mcp"] == "admin_prepare_discover_enable"
