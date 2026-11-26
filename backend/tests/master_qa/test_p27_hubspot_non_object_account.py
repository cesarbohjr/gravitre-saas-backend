"""Regression: malformed HubSpot account response must never reach a write."""
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "scripts"
import sys
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("p27_hubspot_sandbox_readback", SCRIPT_DIR / "p27_hubspot_sandbox_readback.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("response", [None, [], "unexpected", 123, True])
def test_account_response_must_be_object_before_any_write(response):
    calls = []

    def fake_request(url, *, token, method, payload=None):
        calls.append((method, url))
        return response

    with patch.object(module, "_request", side_effect=fake_request):
        with pytest.raises(RuntimeError, match="non-object JSON response"):
            module.verify_hubspot(
                token="synthetic-token-value",
                portal_id=module.GRAVITRE_HUBSPOT_PORTAL_ID,
                email_domain="qa.example.test",
                approved=True,
                approve_existing_live_portal=True,
            )
    assert len(calls) == 1
    assert calls[0][0] == "GET"
    assert calls[0][1].endswith("/account-info/v3/details")
