import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.turn_read_memo import begin_turn_memo, end_turn_memo
from app.services.domain_intelligence_service import DomainIntelligenceService


@pytest.mark.asyncio
async def test_domain_lookup_is_offloaded_memoized_and_org_scoped(monkeypatch):
    client = Mock()
    query = client.table.return_value.select.return_value.eq.return_value.limit.return_value
    query.execute.return_value = SimpleNamespace(data=[{"settings": {"industry": "software"}}])
    monkeypatch.setattr("app.services.domain_intelligence_service.get_supabase_client", lambda _: client)
    monkeypatch.setattr("app.core.db.is_shared_service_client", lambda candidate: candidate is client)
    offload = AsyncMock(side_effect=lambda execute: execute())
    monkeypatch.setattr("app.core.io_pool.run_io", offload)
    service = DomainIntelligenceService(settings=Mock())
    begin_turn_memo()
    try:
        a, b = await asyncio.gather(service._load_org_domain_hints("org-a"), service._load_org_domain_hints("org-a"))
        assert a["industry_raw"] == b["industry_raw"] == "software"
        offload.assert_awaited_once()
        await service._load_org_domain_hints("org-b")
        assert offload.await_count == 2
        assert client.table.return_value.select.return_value.eq.call_args.args == ("id", "org-b")
    finally:
        end_turn_memo()
    await service._load_org_domain_hints("org-a")
    assert offload.await_count == 3
