from uuid import UUID
from unittest.mock import MagicMock
import httpx
import pytest
from fastapi import HTTPException
from app.routers.connectors import _delete_connector_impl, ConnectorDeleteRequest
from app.routers import connectors as routes
from app.connectors import nango_client
from tests.routers.test_managed_connector_flow import Query, row


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [None, ValueError('not configured'), httpx.ConnectError('offline')])
async def test_confirmed_removal_cleans_nango_or_retains_for_retry(monkeypatch,error):
    from types import SimpleNamespace
    cid = UUID('11111111-1111-1111-1111-111111111111')
    store = [row(id=str(cid))]
    client = SimpleNamespace(table=lambda name: Query(store if name == 'connectors' else []))
    monkeypatch.setattr(routes,'create_client',lambda *a: client)
    monkeypatch.setattr(routes,'write_audit_event',lambda *a,**kw: None)
    delete = MagicMock(side_effect=error)
    monkeypatch.setattr(nango_client,'delete_managed_connection',delete)
    settings = SimpleNamespace(supabase_url='https://example.supabase.co',supabase_service_role_key='service')
    if error:
        with pytest.raises(HTTPException) as exc:
            await _delete_connector_impl(cid,ConnectorDeleteRequest(confirmName='desk'),({'user_id':'u1'},'o1'),settings)
        assert exc.value.status_code == 502
        assert store[0]['deleted_at'] is None and store[0]['status'] == 'active'
    else:
        assert await _delete_connector_impl(cid,ConnectorDeleteRequest(confirmName='desk'),({'user_id':'u1'},'o1'),settings) == {'success':True}
        assert store[0]['deleted_at'] and store[0]['status'] == 'disconnected'
    assert delete.call_args.kwargs == {'connection_id':'n1','integration_id':'freshservice'}
