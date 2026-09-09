"""Admin knowledge-graph traverse route."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_knowledge_graph_traverse_admin_delegates_to_service():
    from app.routers.admin_intelligence import traverse_knowledge_graph_admin

    mock_result = {
        "startEntityType": "glossary_term",
        "startEntityId": "term-1",
        "paths": [],
    }
    with patch("app.services.knowledge_graph_service.get_knowledge_graph_service") as get_svc:
        svc = get_svc.return_value
        svc.traverse_multi_hop = AsyncMock(return_value=mock_result)
        out = await traverse_knowledge_graph_admin(
            org_id="org-1",
            _admin=(object(), object()),
            entity_type="glossary_term",
            entity_id="term-1",
            max_hops=2,
            settings=object(),
        )
    assert out == mock_result
    svc.traverse_multi_hop.assert_awaited_once()
