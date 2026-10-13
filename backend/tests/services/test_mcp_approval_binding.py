"""MCP write approvals are bound to the approved input and are single-use."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client_service import MCPClientService, mcp_input_sha256

_WRITE_TOOL = {
    "id": "tool-write",
    "server_id": "srv-1",
    "tool_name": "create_record",
    "capability_tier": "write",
    "enabled": True,
}
_SERVER = {"id": "srv-1", "server_url": "https://93.184.216.34/mcp", "transport": "streamable_http", "enabled": True, "auth_config": {}}


class _Approvals:
    """Minimal approvals table: select by id/org, conditional consume update."""

    def __init__(self, row: dict, *, consume_error: Exception | None = None) -> None:
        self.row = row
        self.consume_error = consume_error
        self.updates: list[dict] = []

    def table(self) -> MagicMock:
        mock = MagicMock()
        mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            dict(self.row)
        ]

        def _update(payload):
            chain = MagicMock()
            filters: dict[str, object] = {}

            def _eq(col, val):
                filters[col] = val
                return chain

            def _is(col, val):
                filters[col] = None if val == "null" else val
                return chain

            def _execute():
                if self.consume_error is not None:
                    raise self.consume_error
                self.updates.append(dict(payload))
                if "status" in filters and self.row.get("status") != filters["status"]:
                    return SimpleNamespace(data=[])
                if "consumed_at" in filters and self.row.get("consumed_at") != filters["consumed_at"]:
                    return SimpleNamespace(data=[])
                self.row["consumed_at"] = payload["consumed_at"]
                return SimpleNamespace(data=[dict(self.row)])

            chain.eq.side_effect = _eq
            chain.is_.side_effect = _is
            chain.execute.side_effect = _execute
            return chain

        mock.update.side_effect = _update
        return mock


def _client(approvals: _Approvals) -> MagicMock:
    client = MagicMock()

    def table(name):
        mock = MagicMock()
        if name == "mcp_tools":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                _WRITE_TOOL
            ]
        elif name == "mcp_servers":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                _SERVER
            ]
        elif name == "approvals":
            return approvals.table()
        return mock

    client.table.side_effect = table
    return client


@pytest.fixture
def service() -> MCPClientService:
    return MCPClientService(settings=SimpleNamespace(connector_secrets_encryption_key="k" * 32))


def _approval(args: dict, **extra) -> dict:
    return {
        "id": "appr-1",
        "status": "approved",
        "consumed_at": None,
        "context": {"mcp_tool_id": "tool-write", "input_sha256": mcp_input_sha256(args), **extra},
    }


async def _run(service, client, args):
    call = AsyncMock(return_value={"created": True})
    with (
        patch.object(service, "_client", return_value=client),
        patch.object(service, "_call_mcp_server", new=call),
        patch.object(service, "_audit_execution", new=AsyncMock()),
        patch.object(service, "_log_execution", new=AsyncMock()),
    ):
        try:
            result = await service.execute_tool("tool-write", "org-1", args, approval_id="appr-1")
        except ValueError as exc:
            result = {"status": "rejected", "error": str(exc)}
    return result, call


def test_input_hash_is_canonical() -> None:
    assert mcp_input_sha256({"a": 1, "b": [1, 2]}) == mcp_input_sha256({"b": [1, 2], "a": 1})
    assert mcp_input_sha256({"a": 1}) != mcp_input_sha256({"a": 2})


@pytest.mark.asyncio
async def test_pending_approval_records_input_hash(service) -> None:
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "exec-1"}]
    with (
        patch.object(service, "_client", return_value=client),
        patch.object(service, "_load_tool", new=AsyncMock(return_value=_WRITE_TOOL)),
        patch(
            "app.services.mcp_client_service.create_contract_approval",
            return_value={"id": "appr-1"},
        ) as create,
    ):
        result = await service.execute_tool("tool-write", "org-1", {"name": "x"})
    assert result["status"] == "pending_approval"
    assert create.call_args.kwargs["context"]["input_sha256"] == mcp_input_sha256({"name": "x"})


@pytest.mark.asyncio
async def test_approved_matching_input_executes_and_consumes(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    result, call = await _run(service, _client(approvals), {"name": "x"})
    assert result["status"] == "completed"
    call.assert_awaited_once()
    assert approvals.row["consumed_at"]


@pytest.mark.asyncio
async def test_approval_replayed_with_different_input_rejected(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    result, call = await _run(service, _client(approvals), {"name": "DROP EVERYTHING"})
    assert result["status"] == "rejected"
    call.assert_not_awaited()
    assert approvals.row["consumed_at"] is None


@pytest.mark.asyncio
async def test_approval_cannot_be_reused(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    first, _ = await _run(service, _client(approvals), {"name": "x"})
    assert first["status"] == "completed"
    second, call = await _run(service, _client(approvals), {"name": "x"})
    assert second["status"] == "rejected"
    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_approval_without_hash_fails_closed(service) -> None:
    row = _approval({"name": "x"})
    row["context"].pop("input_sha256")
    approvals = _Approvals(row)
    result, call = await _run(service, _client(approvals), {"name": "x"})
    assert result["status"] == "rejected"
    call.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_consumed_at_column_fails_closed(service) -> None:
    approvals = _Approvals(
        _approval({"name": "x"}),
        consume_error=Exception("{'code': '42703', 'message': 'column approvals.consumed_at does not exist'}"),
    )
    result, call = await _run(service, _client(approvals), {"name": "x"})
    assert result["status"] == "rejected"
    call.assert_not_awaited()


async def _run_with(service, approvals, *, call=None, load_server=None, log=None):
    patches = [
        patch.object(service, "_client", return_value=_client(approvals)),
        patch.object(service, "_call_mcp_server", new=call or AsyncMock(return_value={"created": True})),
        patch.object(service, "_audit_execution", new=AsyncMock()),
        patch.object(service, "_log_execution", new=log or AsyncMock()),
    ]
    if load_server is not None:
        patches.append(patch.object(service, "_load_server", new=load_server))
    for p in patches:
        p.start()
    try:
        return await service.execute_tool("tool-write", "org-1", {"name": "x"}, approval_id="appr-1")
    finally:
        for p in patches:
            p.stop()


@pytest.mark.asyncio
async def test_server_error_keeps_approval_consumed(service) -> None:
    """The remote write may have landed before the error, so no second run on this approval."""
    approvals = _Approvals(_approval({"name": "x"}))
    result = await _run_with(service, approvals, call=AsyncMock(side_effect=RuntimeError("boom")))
    assert result["status"] == "failed"
    assert approvals.row["consumed_at"] is not None


@pytest.mark.asyncio
async def test_remote_success_then_transport_error_cannot_replay(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    remote_writes: list[dict] = []

    async def write_then_drop(_server, _name, args):
        remote_writes.append(args)
        raise ConnectionResetError("connection dropped after the write")

    first = await _run_with(service, approvals, call=AsyncMock(side_effect=write_then_drop))
    assert first["status"] == "failed"
    second, call = await _run(service, _client(approvals), {"name": "x"})
    assert second["status"] == "rejected"
    call.assert_not_awaited()
    assert len(remote_writes) == 1


@pytest.mark.asyncio
async def test_approval_stays_consumed_when_logging_fails_after_server_returned(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    log = AsyncMock(side_effect=[RuntimeError("log insert failed"), None])
    result = await _run_with(service, approvals, log=log)
    assert result["status"] == "failed"
    assert approvals.row["consumed_at"] is not None


@pytest.mark.asyncio
async def test_approval_stays_consumed_on_timeout(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    result = await _run_with(service, approvals, call=AsyncMock(side_effect=TimeoutError()))
    assert result["status"] == "failed"
    assert approvals.row["consumed_at"] is not None


@pytest.mark.asyncio
async def test_pre_dispatch_failure_releases_approval(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    call = AsyncMock()
    with pytest.raises(ValueError):
        await _run_with(
            service, approvals, call=call, load_server=AsyncMock(side_effect=ValueError("MCP server not found"))
        )
    call.assert_not_awaited()
    assert approvals.row["consumed_at"] is None


@pytest.mark.asyncio
async def test_release_cannot_undo_another_callers_claim(service) -> None:
    approvals = _Approvals(_approval({"name": "x"}))
    with patch.object(service, "_client", return_value=_client(approvals)):
        token = await service._verify_approval("appr-1", "tool-write", "org-1", {"name": "x"})
        # A concurrent caller loses the conditional claim.
        with pytest.raises(ValueError, match="already been used"):
            await service._verify_approval("appr-1", "tool-write", "org-1", {"name": "x"})
        # A stale release (another caller's token) leaves the live claim in place.
        await service._release_approval("appr-1", "org-1", "2000-01-01T00:00:00+00:00")
        assert approvals.row["consumed_at"] == token
        await service._release_approval("appr-1", "org-1", token)
    assert approvals.row["consumed_at"] is None
