import hashlib,hmac
import pytest
from unittest.mock import MagicMock,patch
from app.plays.prospecting_webhook_auth import verify_hmac_sha256,ingest_verified_event

def test_signed_body_is_required():
    body=b'{"event":"sent"}'
    sig=hmac.new(b"secret",body,hashlib.sha256).hexdigest()
    assert verify_hmac_sha256(body,"sha256="+sig,"secret")
    assert not verify_hmac_sha256(body+b" ","sha256="+sig,"secret")
    assert not verify_hmac_sha256(body,"sha256="+sig,"")

def test_unverified_webhook_cannot_query_any_tenant():
    db=MagicMock()
    with pytest.raises(PermissionError):
        ingest_verified_event(db,body=b"{}",signature="invalid",secret="secret",
          provider="smartlead",event_id="1",lead_id="2",event_type="sent")
    db.table.assert_not_called()
