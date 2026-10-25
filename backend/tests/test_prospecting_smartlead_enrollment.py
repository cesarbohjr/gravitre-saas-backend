from unittest.mock import MagicMock,patch
import pytest
from app.plays.prospecting_smartlead_enrollment import enroll_approved_smartlead_lead

BASE=dict(settings=object(),org_id="org",run_id="run",actor_id="actor",
 connector_id="conn",campaign_id="42",prospect_contact_id="contact",
 recipient_email="test@example.ca")

def test_unowned_contact_blocks_nango_and_network():
    db=MagicMock()
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data=[]
    with patch("app.plays.prospecting_smartlead_enrollment.proxy_request") as call:
        with pytest.raises(PermissionError):
            enroll_approved_smartlead_lead(client=db,**BASE)
        call.assert_not_called()

def test_bad_campaign_rejected_before_database_or_network():
    db=MagicMock()
    with pytest.raises(ValueError):
        enroll_approved_smartlead_lead(client=db,**(BASE|{"campaign_id":"../other"}))
    db.table.assert_not_called()
