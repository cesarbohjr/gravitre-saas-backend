from app.capabilities.mcp_activation import package_mcp_server_name


def test_package_mcp_server_names_are_namespaced_by_package() -> None:
    a = package_mcp_server_name("crm", "aaaaaaaa-1111-2222-3333-444444444444")
    b = package_mcp_server_name("crm", "bbbbbbbb-1111-2222-3333-444444444444")
    assert a != b
    assert a.startswith("crm")
    assert b.startswith("crm")
