"""Disposable acceptance fixtures around the pinned, GET-only deployed QA probe.

Only the allowlisted acceptance project may receive fixture writes. Credentials
and sessions stay in memory. The private recovery journal contains synthetic
identifiers only; it is never uploaded as evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

ACCEPTANCE = "https://aadnwmjzrmbvadszroqt.supabase.co"
QA_ORIGIN = "https://eco001-fastapi-qa.up.railway.app"
DEPLOYED_SHA = "c10d8a764f67c428adc408d65429149e7686498f"
PROBE_HASH = "347761a26bc874a0d885b0a463797708661bcb6fac9cbf5fdc047e9dfeb4ae82"


class GateError(Exception):
    """Fixed diagnostic only: never include upstream bodies or credentials."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(method, url, key, *, bearer=None, body=None):
    if not url.startswith(ACCEPTANCE + "/"):
        raise GateError("refused_non_acceptance_request")
    headers = {"apikey": key, "Authorization": "Bearer " + (bearer or key)}
    if body is not None:
        headers["Content-Type"] = "application/json"
    headers["Prefer"] = "return=representation"
    req = Request(url, headers=headers, method=method,
                  data=json.dumps(body).encode() if body is not None else None)
    try:
        with build_opener(NoRedirects()).open(req, timeout=20) as response:
            raw = response.read(262144)
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        # Do not read/print the upstream body; Auth errors can contain email.
        return error.code, None
    except (URLError, TimeoutError, OSError, ValueError):
        raise GateError("acceptance_transport_or_json_error") from None


def require(ok, label):
    if not ok:
        raise GateError(label)


def credentials(environment):
    require(environment.get("E2E_SUPABASE_URL") == ACCEPTANCE,
            "dedicated_supabase_target")
    require(environment.get("E2E_SUPABASE_ALLOWED_URL") == ACCEPTANCE,
            "dedicated_supabase_allowlist")
    keys = []
    for name in ("E2E_SUPABASE_ANON_KEY", "E2E_SUPABASE_SERVICE_ROLE_KEY"):
        key = environment.get(name, "").strip()
        require(bool(key) and all(33 <= ord(c) <= 126 for c in key),
                "missing_or_invalid_" + name)
        keys.append(key)
    return keys


def load_probe(path):
    require(hashlib.sha256(path.read_bytes()).hexdigest() == PROBE_HASH,
            "pinned_probe_checksum")
    spec = importlib.util.spec_from_file_location("eco001_pinned_probe", path)
    require(spec is not None and spec.loader is not None, "pinned_probe_import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, value):
    # Private journal/report files are never world-readable on the runner.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)


class Fixture:
    def __init__(self, admin, journal, transport=request):
        self.admin, self.journal, self.transport = admin, journal, transport
        self.state = json.loads(journal.read_text()) if journal.exists() else {
            "tag": "eco001-ci-" + uuid4().hex,
            "user_id": None, "org_id": None,
            "conversation_id": str(uuid4()), "creation_attempted": False,
        }
        require(self.state["tag"].startswith("eco001-ci-") and
                len(self.state["tag"]) == 42, "invalid_fixture_journal")
        for field in ("user_id", "org_id", "conversation_id"):
            if self.state.get(field):
                UUID(self.state[field])

    def auth(self, method, path, body=None):
        return self.transport(method, ACCEPTANCE + "/auth/v1/" + path,
                              self.admin, body=body)

    def rows(self, table, filters, method="GET", body=None):
        return self.transport(method, ACCEPTANCE + "/rest/v1/" + table + "?" +
                              urlencode(filters), self.admin, body=body)

    def read(self, table, filters):
        status, rows = self.rows(table, filters)
        require(status == 200 and isinstance(rows, list), "read_" + table)
        return rows

    def discover_org(self):
        user = self.state["user_id"]
        rows = self.read("organization_members", {"user_id": "eq." + user,
                                                   "select": "org_id"})
        require(len(rows) == 1, "fixture_membership_count")
        org = str(UUID(rows[0]["org_id"]))
        owned = self.read("organizations", {"id": "eq." + org,
                                              "name": "eq." + self.state["tag"],
                                              "select": "id"})
        require(len(owned) == 1, "fixture_org_identity")
        self.state["org_id"] = org
        save(self.journal, self.state)

    def create(self):
        tag = self.state["tag"]
        password = secrets.token_urlsafe(40)
        self.state["creation_attempted"] = True
        save(self.journal, self.state)
        status, user = self.auth("POST", "admin/users", {
            "email": tag + "@example.invalid", "password": password,
            "email_confirm": True, "user_metadata": {"company_name": tag},
        })
        require(status in (200, 201) and isinstance(user, dict) and user.get("id"),
                "fixture_auth_create")
        self.state["user_id"] = str(UUID(user["id"]))
        save(self.journal, self.state)
        # The actual project's Auth trigger provisions the org/profile/member.
        # Reuse those exact new rows rather than creating another workspace.
        self.discover_org()
        status, _ = self.rows("conversations", {}, "POST", {
            "id": self.state["conversation_id"], "org_id": self.state["org_id"],
            "user_id": self.state["user_id"], "title": tag, "task_state": {},
        })
        require(status == 201, "fixture_conversation_create")
        self.assert_unmodified()
        return tag + "@example.invalid", password

    def assert_unmodified(self):
        rows = self.read("conversations", {
            "id": "eq." + self.state["conversation_id"],
            "org_id": "eq." + self.state["org_id"],
            "user_id": "eq." + self.state["user_id"],
            "select": "id,task_state,message_count,title",
        })
        require(len(rows) == 1 and rows[0]["task_state"] == {} and
                rows[0]["message_count"] == 0 and rows[0]["title"] == self.state["tag"],
                "fixture_state_changed")

    def cleanup(self):
        errors = []
        user, org, conversation = (self.state.get(k) for k in
                                    ("user_id", "org_id", "conversation_id"))
        # A lost create response is ambiguous. Never claim clean in that case.
        if self.state["creation_attempted"] and not user:
            raise GateError("cleanup_auth_create_unacknowledged")
        if user and not org:
            self.discover_org()
            org = self.state["org_id"]
        if user:
            status, actor = self.auth("GET", "admin/users/" + user)
            require(status == 404 or (
                status == 200 and isinstance(actor, dict) and
                actor.get("email") == self.state["tag"] + "@example.invalid" and
                actor.get("user_metadata", {}).get("company_name") == self.state["tag"]
            ), "cleanup_auth_identity_changed")
        if org:
            owned = self.read("organizations", {"id": "eq." + org,
                                                  "select": "id,name"})
            require(not owned or owned[0]["name"] == self.state["tag"],
                    "cleanup_org_identity_changed")
            members = self.read("organization_members", {"org_id": "eq." + org,
                                                            "select": "user_id"})
            require(all(row["user_id"] == user for row in members),
                    "cleanup_foreign_member_refused")
            status, _ = self.rows("organizations", {"id": "eq." + org,
                                                       "name": "eq." + self.state["tag"]},
                                  "DELETE")
            if status not in (200, 204):
                errors.append("cleanup_org_delete")
        if user:
            status, _ = self.auth("DELETE", "admin/users/" + user)
            if status not in (200, 204, 404):
                errors.append("cleanup_auth_delete")
        # Verify the actual persisted rows are absent, including trigger rows.
        checks = [("conversations", "id", conversation)]
        if org:
            checks += [("organizations", "id", org), ("org_billing", "org_id", org),
                       ("environments", "org_id", org)]
        if user:
            checks += [("organization_members", "user_id", user),
                       ("users", "auth_user_id", user)]
        for table, column, identifier in checks:
            if identifier and self.read(table, {column: "eq." + identifier,
                                                "select": "*", "limit": "1"}):
                errors.append("cleanup_remaining_" + table)
        if user:
            status, _ = self.auth("GET", "admin/users/" + user)
            if status != 404:
                errors.append("cleanup_auth_readback")
        require(not errors, ",".join(errors))
        return {"verified": True, "remaining_fixture_rows": 0,
                "auth_user_absent": True, "trigger_rows_absent": True}


def execute(probe, fixture, anon, transport=request):
    report = {"pass": False, "provider_write_performed": False,
              "qa_api_methods": ["GET"], "fixture_writes": "acceptance_project_only",
              "fixture_tag": fixture.state["tag"], "cleanup": {"verified": False}}
    token = refresh = None
    try:
        # No Auth or fixture writes until the existing deployment gate passes.
        report["unsigned_preflight"] = probe.run(QA_ORIGIN, DEPLOYED_SHA, {})
        require(report["unsigned_preflight"].get("pass") is True, "unsigned_preflight_not_passed")
        email, password = fixture.create()
        status, session = transport("POST", ACCEPTANCE + "/auth/v1/token?grant_type=password",
                                    anon, body={"email": email, "password": password})
        require(status == 200 and isinstance(session, dict), "fixture_sign_in")
        token, refresh = session.get("access_token"), session.get("refresh_token")
        require(bool(token) and bool(refresh), "fixture_session_missing")
        status, user = transport("GET", ACCEPTANCE + "/auth/v1/user", anon, bearer=token)
        require(status == 200 and isinstance(user, dict) and
                user.get("id") == fixture.state["user_id"], "fixture_session_identity")
        report["signed_preflight"] = probe.run(
            QA_ORIGIN, DEPLOYED_SHA, {}, qa_bearer=token,
            qa_conversation=fixture.state["conversation_id"])
        require(report["signed_preflight"].get("pass") is True, "signed_preflight_not_passed")
        fixture.assert_unmodified()
        report["fixture_state_unchanged"] = True
        report["pass"] = True
    except Exception as error:
        report["failure"] = str(error) if isinstance(error, GateError) else "deployed_preflight_failed"
    finally:
        # Revoke refresh sessions before deleting the actor. Existing JWTs may
        # remain cryptographically valid until expiry; row deletion fences reads.
        if token:
            try:
                status, _ = transport("POST", ACCEPTANCE + "/auth/v1/logout?scope=global",
                                      anon, bearer=token)
                require(status in (200, 204), "fixture_sign_out")
                report["session_signed_out"] = True
            except Exception:
                report["pass"] = False
                report["session_signed_out"] = False
        try:
            report["cleanup"] = fixture.cleanup()
        except Exception as error:
            report["pass"] = False
            report["cleanup"]["failure"] = str(error) if isinstance(error, GateError) else "cleanup_failed"
        if refresh:
            try:
                status, _ = transport("POST", ACCEPTANCE + "/auth/v1/token?grant_type=refresh_token",
                                      anon, body={"refresh_token": refresh})
                require(status in (400, 401, 403), "refresh_session_still_usable")
                report["refresh_session_revoked"] = True
            except Exception:
                report["pass"] = False
                report["refresh_session_revoked"] = False
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    report = {"pass": False, "cleanup": {"verified": False},
              "provider_write_performed": False}
    try:
        anon, admin = credentials(os.environ)
        probe = load_probe(args.probe)
        fixture = Fixture(admin, args.journal)
        if args.cleanup_only:
            report = json.loads(args.output.read_text()) if args.output.exists() else report
            report["cleanup"] = fixture.cleanup()
        else:
            report = execute(probe, fixture, anon)
    except Exception as error:
        report["pass"] = False
        report["failure"] = str(error) if isinstance(error, GateError) else "fixture_harness_failed"
    save(args.output, report)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["pass"] and report["cleanup"]["verified"] else 1


if __name__ == "__main__":
    # Let finally cleanup run on a runner's ordinary termination request.
    def terminated(*_):
        raise RuntimeError("fixture_run_terminated")
    signal.signal(signal.SIGTERM, terminated)
    raise SystemExit(main())
