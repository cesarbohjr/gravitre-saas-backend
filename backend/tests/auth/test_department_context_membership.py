"""X-Department is only honoured for members (or admins) of that department."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.auth.dependencies import get_department_context

USER = {"user_id": "user-1"}
DEPTS = [
    {"id": "d-sales", "name": "Sales", "department_admin_id": None},
    {"id": "d-fin", "name": "Finance", "department_admin_id": "user-1"},
]


def _client(*, role: str = "member", memberships: list[str] | None = None) -> MagicMock:
    client = MagicMock()

    def table(name):
        mock = MagicMock()
        if name == "organization_members":
            mock.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = (
                SimpleNamespace(data=[{"role": role}])
            )
        elif name == "departments":
            mock.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=DEPTS)
        elif name == "department_members":
            rows = [{"department_id": d} for d in (memberships or [])]
            mock.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = (
                SimpleNamespace(data=rows)
            )
        return mock

    client.table.side_effect = table
    return client


async def _resolve(header: str | None, client: MagicMock, org_id: str | None = "org-1"):
    with patch("app.auth.dependencies._get_cached_service_client", return_value=client):
        return await get_department_context(
            current_user=USER, org_id=org_id, settings=MagicMock(), x_department=header
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "", "all", "*"])
async def test_no_department_scope_needs_no_lookup(header) -> None:
    client = _client()
    assert await _resolve(header, client) is None
    client.table.assert_not_called()


@pytest.mark.asyncio
async def test_member_of_department_is_allowed() -> None:
    assert await _resolve("sales", _client(memberships=["d-sales"])) == "sales"


@pytest.mark.asyncio
async def test_department_admin_is_allowed() -> None:
    assert await _resolve("Finance", _client()) == "Finance"


@pytest.mark.asyncio
async def test_org_admin_is_allowed() -> None:
    assert await _resolve("Sales", _client(role="admin")) == "Sales"


@pytest.mark.asyncio
async def test_non_member_header_is_ignored() -> None:
    assert await _resolve("Sales", _client(memberships=[])) is None


@pytest.mark.asyncio
async def test_unknown_department_header_is_ignored() -> None:
    assert await _resolve("Legal", _client(memberships=["d-sales"])) is None


@pytest.mark.asyncio
async def test_department_without_org_context_is_ignored() -> None:
    assert await _resolve("Sales", _client(memberships=["d-sales"]), org_id=None) is None
