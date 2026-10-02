from __future__ import annotations

import hashlib
import hmac

from app.routers.managed_connector_auth import _verify_nango_webhook_signature


def test_verify_nango_webhook_signature_accepts_hmac_sha256() -> None:
    body = b'{"type":"auth","success":true}'
    key = "webhook-signing-key"
    signature = hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert _verify_nango_webhook_signature(body, signature, key) is True


def test_verify_nango_webhook_signature_fails_closed() -> None:
    body = b'{"type":"auth","success":true}'
    assert _verify_nango_webhook_signature(body, None, "key") is False
    assert _verify_nango_webhook_signature(body, "bad", "key") is False
    assert _verify_nango_webhook_signature(body, "bad", "") is False
