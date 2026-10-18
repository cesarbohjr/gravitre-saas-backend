"""Real authenticated local PostgREST isolation checks.

Creates two independent disposable Auth sessions. This tests the actual
PostgREST boundary, not merely SET ROLE impersonation. Never targets production.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse

import pytest


def _local_status():
    directory = os.environ.get("MSP_TEST_PROJECT_DIR", "")
    if not directory or not directory.startswith("/"):
        pytest.fail("Disposable MSP_TEST_PROJECT_DIR is required")
    output = subprocess.run(
        ["supabase", "status", "-o", "env"], cwd=directory,
        capture_output=True, text=True, check=True,
    ).stdout
    values = {}
    for line in output.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"')
    base = values.get("API_URL", "")
    anon = values.get("ANON_KEY", "")
    url = urlparse(base)
    if (url.hostname, url.port) != ("127.0.0.1", 54321) or not anon:
        pytest.fail("Must use local Supabase API and its disposable anon key")
    return base, anon


def _request(url, method, key, token=None, data=None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"apikey": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def _session(base, anon):
    email = "msp-isolation-" + uuid.uuid4().hex + "@example.test"
    password = "MspLocalSecurity!" + uuid.uuid4().hex
    status, signup = _request(
        base + "/auth/v1/signup", "POST", anon,
        data={"email": email, "password": password},
    )
    assert status in (200, 201), ("Local signup unexpectedly failed", status, signup)
    status, login = _request(
        base + "/auth/v1/token?grant_type=password", "POST", anon,
        data={"email": email, "password": password},
    )
    assert status == 200 and login.get("access_token"), (
        "Local email confirmation must be disabled for disposable test clients",
        status, login,
    )
    return login["access_token"]


def test_two_real_authenticated_clients_cannot_reach_msp_grants_or_revoke_rpc():
    base, anon = _local_status()
    tokens = [_session(base, anon), _session(base, anon)]
    assert tokens[0] != tokens[1]
    for token in tokens:
        status, response = _request(
            base + "/rest/v1/msp_delegations?select=*", "GET", anon, token
        )
        assert status in (401, 403), ("Read must be forbidden", status, response)
        status, response = _request(
            base + "/rest/v1/msp_delegations", "POST", anon, token,
            data={"provider_org_id": str(uuid.uuid4()),
                  "customer_org_id": str(uuid.uuid4()),
                  "grantee_user_id": str(uuid.uuid4()), "tier": 3,
                  "approved_by_customer_user_id": str(uuid.uuid4()),
                  "expires_at": "2099-01-01T00:00:00Z"},
        )
        assert status in (401, 403), ("Write must be forbidden", status, response)
        status, response = _request(
            base + "/rest/v1/rpc/msp_revoke_delegation_atomic", "POST", anon, token,
            data={"p_delegation_id": str(uuid.uuid4()),
                  "p_customer_org_id": str(uuid.uuid4()),
                  "p_actor_user_id": str(uuid.uuid4())},
        )
        assert status in (401, 403, 404), ("Revocation RPC must be forbidden", status, response)
