from app.capabilities.mcp_activation import deactivate_package_mcp_dependencies, declared_mcp_dependencies, prepare_mcp_dependencies


def test_remote_https_mcp_dependency_can_be_prepared() -> None:
    rows = declared_mcp_dependencies(
        {"mcpServers": {"crm": {"url": "https://mcp.example.com", "transport": "http"}}}
    )
    assert rows[0]["registrationAllowed"] is True


def test_stdio_mcp_dependency_is_not_auto_registered() -> None:
    rows = declared_mcp_dependencies(
        {"mcpServers": {"local": {"command": "node", "args": ["server.js"], "transport": "stdio"}}}
    )
    assert rows[0]["registrationAllowed"] is False
    assert "local/stdio" in rows[0]["blockedReason"]


def test_private_network_mcp_dependency_is_blocked() -> None:
    rows = declared_mcp_dependencies(
        {"mcpServers": {"private": {"url": "https://10.0.0.2/mcp", "transport": "http"}}}
    )
    assert rows[0]["registrationAllowed"] is False


def test_unsupported_streamable_transport_is_blocked_until_runtime_supports_it() -> None:
    rows = declared_mcp_dependencies(
        {
            "mcpServers": {
                "future": {
                    "url": "https://mcp.example.com/mcp",
                    "transport": "streamable_http",
                }
            }
        }
    )
    assert rows[0]["registrationAllowed"] is False


class _Query:
    def __init__(self, rows=None):
        self.rows = rows or []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.rows = [{**payload, "id": "server-1"}]
        return self

    def execute(self):
        class Result:
            data = self.rows
        return Result()


class _Client:
    def table(self, name: str):
        assert name == "mcp_servers"
        return _Query([])


def test_prepare_mcp_dependencies_returns_pending_review_and_never_enables() -> None:
    result = prepare_mcp_dependencies(
        _Client(),
        org_id="org-1",
        package_id="pkg-1",
        manifest={
            "mcpServers": {
                "crm": {
                    "url": "https://mcp.example.com/mcp",
                    "transport": "http",
                }
            }
        },
        user_id="user-1",
    )

    assert result["activationState"] == "pending_review"
    assert result["enabled"] == 0
    assert result["credentialsCopiedFromPackage"] is False
    assert result["prepared"][0]["enabled"] is False
    assert result["prepared"][0]["activation_state"] == "pending_review"


class _DeactivateQuery:
    def __init__(self, client, table_name: str):
        self.client = client
        self.table_name = table_name
        self.payload = None
        self.filters = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def update(self, payload):
        self.payload = payload
        self.client.updates.append((self.table_name, payload))
        return self

    def execute(self):
        class Result:
            data = (
                [{"id": "server-1"}]
                if self.table_name == "mcp_servers" and self.payload is None
                else []
            )
        return Result()


class _DeactivateClient:
    def __init__(self):
        self.updates = []

    def table(self, name: str):
        return _DeactivateQuery(self, name)


def test_deactivate_package_mcp_dependencies_disables_server_and_tools() -> None:
    client = _DeactivateClient()
    result = deactivate_package_mcp_dependencies(
        client,
        org_id="org-1",
        package_id="pkg-1",
        activation_state="quarantined",
    )

    assert result["disabledServers"] == 1
    assert ("mcp_servers", {"enabled": False, "activation_state": "quarantined"}) in client.updates
    assert ("mcp_tools", {"enabled": False}) in client.updates
