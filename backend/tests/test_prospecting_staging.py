from unittest.mock import MagicMock
import pytest
from app.plays.prospecting_staging import stage_reviewed_contact

def test_requires_tenant():
    with pytest.raises(ValueError):
        stage_reviewed_contact(MagicMock(),org_id="",contact_id="x",actor_id="y")

def test_missing_contact_does_not_write_staging():
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    with pytest.raises(LookupError):
        stage_reviewed_contact(client,org_id="tenant-a",contact_id="missing",actor_id="actor-a")
    client.table.return_value.upsert.assert_not_called()
