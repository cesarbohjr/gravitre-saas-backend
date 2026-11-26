"""Fail-closed fixture lifecycle contracts; no hosted credentials or network."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("disposable_probe", ROOT / "scripts/eco001_disposable_preflight.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class API:
    def __init__(self):
        self.calls = []
        self.tables = {k: [] for k in ("organizations", "organization_members", "users", "conversations", "org_billing", "environments")}
        self.user = None
        self.session = False
        self.fail = None
        self.user_id, self.org_id = str(uuid4()), str(uuid4())

    def __call__(self, method, url, key, *, bearer=None, body=None):
        self.calls.append((method, url, key, bearer, body))
        path, query = urlsplit(url).path, parse_qs(urlsplit(url).query)
        if self.fail == (method, path):
            return 503, None
        if path == "/auth/v1/admin/users" and method == "POST":
            self.user = {"id": self.user_id, "email": body["email"], "user_metadata": body["user_metadata"]}
            self.tables["organizations"] = [{"id": self.org_id, "name": body["user_metadata"]["company_name"]}]
            self.tables["organization_members"] = [{"org_id": self.org_id, "user_id": self.user_id}]
            self.tables["users"] = [{"id": str(uuid4()), "auth_user_id": self.user_id, "org_id": self.org_id}]
            self.tables["org_billing"] = [{"org_id": self.org_id}]
            self.tables["environments"] = [{"org_id": self.org_id}]
            return 200, self.user
        if path.startswith("/auth/v1/admin/users/"):
            if method == "DELETE":
                self.user = None
                self.session = False
                self.tables["users"] = []
                self.tables["organization_members"] = []
                return 200, None
            return (200, self.user) if self.user else (404, None)
        if path == "/auth/v1/token":
            if query["grant_type"] == ["refresh_token"]:
                return (200, {}) if self.session else (400, None)
            self.session = True
            return 200, {"access_token": "private.actor.signature", "refresh_token": "private-refresh"}
        if path == "/auth/v1/user":
            return 200, self.user
        if path == "/auth/v1/logout":
            self.session = False
            return 204, None
        table = path.rsplit("/", 1)[-1]
        rows = self.tables[table]
        match = lambda row: all(not v[0].startswith("eq.") or str(row.get(k)) == v[0][3:] for k, v in query.items())
        if method == "POST":
            rows.append({"message_count": 0, **body})
            return 201, [body]
        if method == "DELETE":
            self.tables[table] = [r for r in rows if not match(r)]
            if table == "organizations":
                for k in self.tables:
                    if k != "organizations":
                        self.tables[k] = [r for r in self.tables[k] if r.get("org_id") != self.org_id]
            return 200, []
        return 200, [dict(r) for r in rows if match(r)]


def harness(tmp_path):
    api = API()
    return api, probe.Fixture("private-admin", tmp_path / "journal.json", api)


def successful_probe(*args, **kwargs):
    return {"pass": True, "signed_fixture_statuses": {"anonymous": 401, "authenticated": 200}} if kwargs else {"pass": True}


def test_complete_lifecycle_masks_evidence_and_removes_trigger_rows(tmp_path):
    api, fixture = harness(tmp_path)
    report = probe.execute(SimpleNamespace(run=successful_probe), fixture, "private-anon", api)
    assert report["pass"] and report["cleanup"]["verified"]
    assert report["refresh_session_revoked"] and report["session_signed_out"]
    assert api.user is None and all(not rows for rows in api.tables.values())
    assert fixture.cleanup()["remaining_fixture_rows"] == 0  # recovery is idempotent
    private = ("private-admin", "private-anon", "private-refresh", "private.actor.signature")
    assert all(value not in json.dumps(report) + fixture.journal.read_text() for value in private)
    assert fixture.journal.stat().st_mode & 0o777 == 0o600


def test_deployment_gate_precedes_all_fixture_writes(tmp_path):
    api, fixture = harness(tmp_path)
    def reject(*args, **kwargs):
        raise ValueError("unexpected production runtime")
    report = probe.execute(SimpleNamespace(run=reject), fixture, "anon", api)
    assert not report["pass"] and report["cleanup"]["verified"]
    assert not any(method in ("POST", "DELETE") for method, *_ in api.calls)


def test_failed_deployed_auth_check_still_revokes_and_cleans(tmp_path):
    api, fixture = harness(tmp_path)
    def reject_signed(*args, **kwargs):
        if kwargs:
            raise ValueError("secret upstream error must be omitted")
        return {"pass": True}
    report = probe.execute(SimpleNamespace(run=reject_signed), fixture, "anon", api)
    assert not report["pass"] and report["cleanup"]["verified"]
    assert report["session_signed_out"] and report["refresh_session_revoked"]
    assert "secret upstream" not in json.dumps(report)


@pytest.mark.parametrize("failure", [
    ("POST", "/auth/v1/admin/users"),
    ("POST", "/rest/v1/conversations"),
    ("POST", "/auth/v1/token"),
    ("GET", "/auth/v1/user"),
    ("POST", "/auth/v1/logout"),
    ("DELETE", "/rest/v1/organizations"),
])
def test_lifecycle_failures_cannot_be_reported_as_pass(tmp_path, failure):
    api, fixture = harness(tmp_path)
    api.fail = failure
    report = probe.execute(SimpleNamespace(run=successful_probe), fixture, "anon", api)
    assert not report["pass"]
    if failure == ("POST", "/auth/v1/admin/users"):
        assert not report["cleanup"]["verified"]  # lost creation acknowledgment is unknown
    elif failure == ("DELETE", "/rest/v1/organizations"):
        assert not report["cleanup"]["verified"]
    else:
        assert report["cleanup"]["verified"]


def test_fixture_mutation_is_detected_and_cleaned(tmp_path):
    api, fixture = harness(tmp_path)
    def mutation(*args, **kwargs):
        if kwargs:
            api.tables["conversations"][0]["task_state"] = {"pending_task": {"type": "write"}}
        return {"pass": True}
    report = probe.execute(SimpleNamespace(run=mutation), fixture, "anon", api)
    assert not report["pass"] and report["cleanup"]["verified"]
    assert report["failure"] == "fixture_state_changed"


@pytest.mark.parametrize("change", ["org_name", "foreign_member"])
def test_cleanup_refuses_changed_or_shared_org(tmp_path, change):
    api, fixture = harness(tmp_path)
    fixture.create()
    if change == "org_name":
        api.tables["organizations"][0]["name"] = "unrelated"
    else:
        api.tables["organization_members"].append({"org_id": api.org_id, "user_id": str(uuid4())})
    api.calls.clear()
    with pytest.raises(probe.GateError):
        fixture.cleanup()
    assert not any(method == "DELETE" for method, *_ in api.calls)


def test_redirects_never_receive_credentials():
    assert probe.NoRedirects().redirect_request(None, None, 302, "", {}, "https://other.invalid") is None
    with pytest.raises(probe.GateError, match="non_acceptance"):
        probe.request("POST", "https://production.invalid/auth/v1/token", "private")


@pytest.mark.parametrize("name,value", [
    ("E2E_SUPABASE_URL", "https://production.invalid"),
    ("E2E_SUPABASE_URL", probe.ACCEPTANCE + "/"),
    ("E2E_SUPABASE_ALLOWED_URL", "https://production.invalid"),
    ("E2E_SUPABASE_ANON_KEY", ""),
    ("E2E_SUPABASE_SERVICE_ROLE_KEY", "bad\nheader"),
])
def test_wrong_target_or_missing_key_fails_before_network(name, value):
    environment = {"E2E_SUPABASE_URL": probe.ACCEPTANCE,
                   "E2E_SUPABASE_ALLOWED_URL": probe.ACCEPTANCE,
                   "E2E_SUPABASE_ANON_KEY": "anon", "E2E_SUPABASE_SERVICE_ROLE_KEY": "admin"}
    environment[name] = value
    with pytest.raises(probe.GateError):
        probe.credentials(environment)


def test_changed_probe_source_is_rejected(tmp_path):
    path = tmp_path / "probe.py"
    path.write_text("raise Exception('must never import')")
    with pytest.raises(probe.GateError, match="checksum"):
        probe.load_probe(path)


def test_cleanup_refuses_an_auth_identity_that_no_longer_matches(tmp_path):
    api, fixture = harness(tmp_path)
    fixture.create()
    api.user["email"] = "unrelated@example.invalid"
    api.calls.clear()
    with pytest.raises(probe.GateError, match="auth_identity"):
        fixture.cleanup()
    assert not any(method == "DELETE" for method, *_ in api.calls)


def test_recoverable_cleanup_failure_can_be_retried_without_promoting_failed_probe(tmp_path):
    api, fixture = harness(tmp_path)
    api.fail = ("DELETE", "/rest/v1/organizations")
    report = probe.execute(SimpleNamespace(run=successful_probe), fixture, "anon", api)
    assert not report["pass"] and not report["cleanup"]["verified"]
    api.fail = None
    report["cleanup"] = fixture.cleanup()
    assert not report["pass"] and report["cleanup"]["verified"]


def workflow():
    from runpy import run_path

    contract = run_path(str(ROOT / "scripts/workflow_source_contract.py"))
    return contract["definition"](ROOT, "eco-001-deployed-ingress.yml")


@pytest.mark.parametrize("override", [
    {}, {"EVENT_NAME": "pull_request"}, {"REPOSITORY": "elsewhere/repository"},
    {"ACTOR": "someone-else"}, {"DISPATCH_REF": "refs/heads/unreviewed"},
    {"DISPATCH_REF": "refs/heads/ci/eco001-disposable-signed-preflight"},
    {"DISPATCH_REF": "refs/tags/v1.0.0"},
    {"CONFIRM_DISPOSABLE_FIXTURE": "false"}, {"CONFIRM_DISPOSABLE_FIXTURE": ""},
])
def test_actual_dispatch_guard_is_fail_closed(override):
    env = {"EVENT_NAME": "workflow_dispatch", "REPOSITORY": "cesarbohjr/gravitre-saas-backend",
           "ACTOR": "cesarbohjr", "DISPATCH_REF": "refs/heads/main",
           "CONFIRM_DISPOSABLE_FIXTURE": "true", **override}
    step = workflow()["jobs"]["authorize"]["steps"][0]
    out = subprocess.run(["bash", "-c", step["run"]], env=env, capture_output=True)
    assert out.returncode == (0 if not override else 1)


def test_workflow_uses_existing_credentials_and_always_retains_cleanup_evidence():
    jobs = workflow()["jobs"]
    assert "environment" not in jobs["fixture-contracts"]
    job = jobs["signed-qa-ingress-preflight"]
    assert job["environment"] == "acceptance"
    cleanup, upload = job["steps"][-2:]
    assert cleanup["if"] == upload["if"] == "always()"
    assert "--cleanup-only" in cleanup["run"]
    assert upload["with"]["path"] == "${{ runner.temp }}/eco001-signed-qa-ingress.json"
    assert "private-fixture" not in upload["with"]["path"]
    text = json.dumps(job)
    assert "ECO001_QA_BEARER" not in text and "ECO001_QA_CONVERSATION" not in text
    assert "E2E_SUPABASE_SERVICE_ROLE_KEY" in text
    assert "STRIPE" not in text and "ELEVENLABS" not in text
