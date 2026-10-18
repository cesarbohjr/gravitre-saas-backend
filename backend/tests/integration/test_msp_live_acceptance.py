"""Real Supabase Auth + PostgREST + FastAPI MSP acceptance tests.

Disposable local project ONLY. No mock auth, no mock database, no production.
The FastAPI router is exercised through HTTP ASGI TestClient; every database
operation and both Auth sessions use the running local Supabase services.
"""
import os
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.routers.msp_delegations import router
from test_msp_rest_isolation import _local_status, _request


@pytest.fixture(scope="module")
def live_environment():
    dsn = os.environ.get("MSP_TEST_DATABASE_URL", "")
    url = urlparse(dsn)
    if (url.hostname, url.port, url.path) != ("127.0.0.1", 54322, "/postgres"):
        pytest.fail("MSP acceptance tests must run against disposable local PostgreSQL only")
    base, anon = _local_status()
    status_text = subprocess.run(["supabase", "status", "-o", "env"],
        cwd=os.environ["MSP_TEST_PROJECT_DIR"], check=True,
        capture_output=True, text=True).stdout
    local = dict(line.strip().split("=", 1) for line in status_text.splitlines() if "=" in line)
    service_key = local.get("SERVICE_ROLE_KEY", "").strip('"')
    jwt_secret = local.get("JWT_SECRET", "").strip('"')
    if not service_key or not jwt_secret:
        pytest.fail("Local Supabase service role and JWT secret required")
    # Validate key belongs to local instance, never a remote environment.
    assert base == "http://127.0.0.1:54321"
    settings = SimpleNamespace(
        supabase_url=base,
        supabase_service_role_key=service_key,
        supabase_jwt_secret=jwt_secret,
        supabase_jwt_issuer="",
        supabase_jwt_audience="authenticated",
        supabase_jwt_leeway_seconds=60,
        jwt_issuer=base + "/auth/v1",
        jwt_audience="authenticated",
        msp_parent_org_enabled=True,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client, psycopg.connect(dsn) as db:
        yield client, db, base, anon


def _new_identity(base, anon):
    email = "msp-e2e-" + uuid.uuid4().hex + "@example.test"
    password = "LocalMspOnly!" + uuid.uuid4().hex
    status, data = _request(base + "/auth/v1/signup", "POST", anon,
                            data={"email": email, "password": password})
    assert status in (200, 201), (status, data)
    uid = data.get("user", {}).get("id")
    assert uid, data
    return uid, email, password


def _login(base, anon, email, password):
    status, data = _request(base + "/auth/v1/token?grant_type=password",
                            "POST", anon, data={"email": email, "password": password})
    assert status == 200 and data.get("access_token"), (status, data)
    return data["access_token"]


def _headers(token):
    return {"Authorization": "Bearer " + token}


def _fixture_orgs(db, owner, provider_user):
    provider, customer_a, customer_b = [str(uuid.uuid4()) for _ in range(3)]
    with db.cursor() as cur:
        for oid, label, parent in (
            (provider, "provider", None),
            (customer_a, "customer-a", provider),
            (customer_b, "customer-b", provider),
        ):
            cur.execute(
                "INSERT INTO public.organizations (id,name,slug,status,parent_org_id) "
                "VALUES (%s,%s,%s,'active',%s)",
                (oid, "Disposable MSP " + label, "msp-e2e-" + oid, parent),
            )
        cur.execute(
            "INSERT INTO public.organization_members (org_id,user_id,role) "
            "VALUES (%s,%s,'member'),(%s,%s,'owner'),(%s,%s,'owner')",
            (provider, provider_user, customer_a, owner, customer_b, owner),
        )
    db.commit()
    return provider, customer_a, customer_b


def _request_health(client, customer, provider, token):
    return client.get(
        f"/api/msp/delegations/customer/{customer}/health",
        params={"provider_org_id": provider}, headers=_headers(token),
    )


def _grant(client, provider, customer, grantee, owner_token):
    return client.post(
        "/api/msp/delegations",
        headers=_headers(owner_token),
        json={
            "provider_org_id": provider, "customer_org_id": customer,
            "grantee_user_id": grantee, "tier": 1,
            "actions": ["account.health.read"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )


def _setup(live_environment):
    client, db, base, anon = live_environment
    owner, owner_email, owner_password = _new_identity(base, anon)
    provider_user, provider_email, provider_password = _new_identity(base, anon)
    owner_token = _login(base, anon, owner_email, owner_password)
    session_one = _login(base, anon, provider_email, provider_password)
    session_two = _login(base, anon, provider_email, provider_password)
    assert session_one != session_two, "Sessions must be independently issued tokens"
    provider, customer_a, customer_b = _fixture_orgs(db, owner, provider_user)
    return client, db, owner, provider_user, owner_token, session_one, session_two, provider, customer_a, customer_b


def test_live_authorized_msp_access(live_environment):
    client, db, owner, grantee, owner_token, session_one, session_two, provider, a, b = _setup(live_environment)
    for token in (session_one, session_two):
        assert _request_health(client, a, provider, token).status_code == 403
        assert _request_health(client, b, provider, token).status_code == 403

    response = _grant(client, provider, a, grantee, owner_token)
    assert response.status_code == 201, response.text
    delegation_id = response.json()["id"]
    for token in (session_one, session_two):
        response = _request_health(client, a, provider, token)
        assert response.status_code == 200, response.text
        assert response.json() == {"customer_org_id": a, "status": "active"}
        assert _request_health(client, b, provider, token).status_code == 403
    with db.cursor() as cur:
        cur.execute(
            "SELECT action, actor_user_id FROM public.msp_delegation_audit "
            "WHERE delegation_id=%s", (delegation_id,),
        )
        assert cur.fetchall() == [("grant.created", uuid.UUID(owner))]


def test_live_cross_session_revocation(live_environment):
    client, db, owner, grantee, owner_token, session_one, session_two, provider, a, b = _setup(live_environment)
    response = _grant(client, provider, a, grantee, owner_token)
    assert response.status_code == 201, response.text
    delegation_id = response.json()["id"]
    assert _request_health(client, a, provider, session_one).status_code == 200
    assert _request_health(client, a, provider, session_two).status_code == 200

    revoked = client.post(
        f"/api/msp/delegations/{delegation_id}/revoke",
        params={"customer_org_id": a}, headers=_headers(owner_token),
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["revoked"] is True

    # Same JWTs, same TestClient, no sign-out or re-authentication.
    for token in (session_one, session_two):
        assert _request_health(client, a, provider, token).status_code == 403
        assert _request_health(client, b, provider, token).status_code == 403
    with db.cursor() as cur:
        cur.execute(
            "SELECT action, actor_user_id FROM public.msp_delegation_audit "
            "WHERE delegation_id=%s ORDER BY recorded_at, action", (delegation_id,),
        )
        assert cur.fetchall() == [
            ("grant.created", uuid.UUID(owner)),
            ("grant.revoked", uuid.UUID(owner)),
        ]
        cur.execute("SELECT revoked_at FROM public.msp_delegations WHERE id=%s", (delegation_id,))
        assert cur.fetchone()[0] is not None
