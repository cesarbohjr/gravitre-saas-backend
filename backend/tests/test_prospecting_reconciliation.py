from unittest.mock import MagicMock
import pytest
from app.plays.prospecting_reconciliation import reconcile_reserved_credit

def test_uncertain_credit_requires_verified_evidence():
    with pytest.raises(ValueError):
        reconcile_reserved_credit(MagicMock(),org_id="org",provider="hunter",
            request_id="abc",confirmed_consumed=None,provider_evidence_id="",verified_by="")

def test_cross_tenant_lookup_cannot_settle():
    client=MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    assert not reconcile_reserved_credit(client,org_id="org-a",provider="hunter",
       request_id="other-org-id",confirmed_consumed=0,provider_evidence_id="vendor-confirmation",verified_by="reviewer")
    client.rpc.assert_not_called()
