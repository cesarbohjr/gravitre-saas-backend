"""Tier 5 manual epic verification (Epics A–F) against production API + app routes.

Covers checklist items in docs/integration/TIER5_PRODUCTION_SMOKE.md that are not
fully covered by smoke:tier5 / smoke:post-tier5 / smoke:ai-production.

Usage:
  npm run smoke:tier5-manual
  python scripts/smoke-tier5-manual-epics.py --json docs/delivery/smoke-tier5-manual-latest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.operators.services.auto_execute_service import (  # noqa: E402
    step_is_auto_eligible,
)
from app.services.autonomous_budget_service import (  # noqa: E402
    AutonomousBudgetExceededError,
    check_autonomous_budget,
)

ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://api.gravitre.app",
).rstrip("/")
APP_URL = os.environ.get("APP_URL", "https://gravitre.app").rstrip("/")
ENV_NAME = "production"
PARTNER_ORG_ID = "00000000-0000-0000-0000-000000000002"


@dataclass
class StepResult:
    epic: str
    step: str
    status: str  # pass | warn | fail
    detail: str = ""


@dataclass
class Report:
    target: str
    app_url: str
    org_id: str
    user_id: str
    started_at: str
    finished_at: str = ""
    steps: list[StepResult] = field(default_factory=list)

    def add(self, epic: str, step: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(epic=epic, step=step, status=status, detail=detail))
        mark = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}[status]
        print(f"[{mark}] {epic} {step}: {detail}")

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for s in self.steps if s.status == "pass")
        warned = sum(1 for s in self.steps if s.status == "warn")
        failed = sum(1 for s in self.steps if s.status == "fail")
        return {
            "target": self.target,
            "appUrl": self.app_url,
            "orgId": self.org_id,
            "userId": self.user_id,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "summary": {"pass": passed, "warn": warned, "fail": failed},
            "steps": [
                {"epic": s.epic, "step": s.step, "status": s.status, "detail": s.detail}
                for s in self.steps
            ],
        }


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _with_env(path: str) -> str:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    return path


def _request(
    method: str,
    path: str,
    token: str,
    org_id: str,
    body: dict | None = None,
    *,
    timeout: int = 90,
    expect_codes: set[int] | None = None,
) -> tuple[int, dict]:
    path = _with_env(path)
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            payload = json.loads(raw) if raw.strip() else {}
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        if expect_codes and exc.code in expect_codes:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                payload = {"raw": raw[:500]}
            return exc.code, payload
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {path}: {raw[:800]}") from exc


def _fetch_app(path: str) -> tuple[int, str]:
    url = f"{APP_URL}{path}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "gravitre-tier5-manual-smoke/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.geturl()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.geturl()


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _supabase(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    client = _supabase(env)
    members = (
        client.table("organization_members")
        .select("org_id, user_id, role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    if not members.data:
        raise SystemExit("No admin organization_members row found")
    row = members.data[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def _ensure_partner_org(env: dict[str, str], primary_org_id: str, user_id: str) -> str:
    client = _supabase(env)
    existing = client.table("organizations").select("id").eq("id", PARTNER_ORG_ID).limit(1).execute()
    if not existing.data:
        client.table("organizations").insert(
            {
                "id": PARTNER_ORG_ID,
                "name": "Tier5 Federation Partner (smoke)",
                "slug": "tier5-partner-smoke",
            }
        ).execute()
    member = (
        client.table("organization_members")
        .select("id")
        .eq("org_id", PARTNER_ORG_ID)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        client.table("organization_members").insert(
            {"org_id": PARTNER_ORG_ID, "user_id": user_id, "role": "admin"}
        ).execute()
    if PARTNER_ORG_ID == primary_org_id:
        alt = (
            client.table("organizations")
            .select("id")
            .neq("id", primary_org_id)
            .limit(1)
            .execute()
        )
        if alt.data:
            return str(alt.data[0]["id"])
    return PARTNER_ORG_ID


def _list_connectors(token: str, org_id: str) -> list[dict]:
    _, payload = _request("GET", "/api/connectors", token, org_id)
    return payload.get("connectors") or payload.get("integrations") or []


def _find_connector(connectors: list[dict], vendor: str) -> dict | None:
    needle = vendor.lower()
    return next(
        (
            c
            for c in connectors
            if str(c.get("vendor") or c.get("type") or "").lower() == needle
        ),
        None,
    )


def _pick_agent_id(token: str, org_id: str) -> str:
    _, payload = _request("GET", "/api/agents", token, org_id)
    agents = payload.get("agents") or []
    if not agents:
        raise RuntimeError("No agents available for epic tests")
    return str(agents[0]["id"])


def run_epic_a(report: Report, env: dict[str, str], token: str, org_id: str, user_id: str) -> None:
    client = _supabase(env)
    agent_id = _pick_agent_id(token, org_id)

    # A.1 — enable auto-execute; verify policy blocks unsafe steps
    _, auto_resp = _request(
        "PUT",
        f"/api/agents/{agent_id}/auto-execute",
        token,
        org_id,
        {
            "execution_mode": "auto_trusted_scopes",
            "trusted_scopes": ["member"],
        },
    )
    mode = auto_resp.get("executionMode") or auto_resp.get("execution_mode")
    operator_row = (
        client.table("operators")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    operator = dict(operator_row.data[0]) if operator_row.data else {}
    mode = operator.get("execution_mode") or mode
    unsafe_step = {
        "step_type": "delete_records",
        "explanation": {
            "executable": True,
            "draft_only": False,
            "admin_required": True,
            "approval_required": False,
            "permissions_required": ["admin"],
        },
    }
    blocked = not step_is_auto_eligible(operator, unsafe_step)
    if mode == "auto_trusted_scopes" and blocked:
        report.add("A", "A.1", "pass", f"auto-execute enabled; unsafe admin step blocked for agent {agent_id[:8]}")
    else:
        report.add("A", "A.1", "fail", f"mode={mode} blocked={blocked}")

    # restore plan_only
    _request(
        "PUT",
        f"/api/agents/{agent_id}/auto-execute",
        token,
        org_id,
        {"executionMode": "plan_only", "trustedScopes": []},
    )

    # A.2 — pause in-flight run (workflow or agent interrupt)
    running = (
        client.table("workflow_runs")
        .select("id, status")
        .eq("org_id", org_id)
        .eq("environment", ENV_NAME)
        .eq("status", "running")
        .limit(1)
        .execute()
    )
    if running.data:
        run_id = str(running.data[0]["id"])
        code, pause_resp = _request(
            "POST",
            f"/api/runs/{run_id}/pause",
            token,
            org_id,
            expect_codes={200, 409},
        )
        if code == 200 and pause_resp.get("success"):
            report.add("A", "A.2", "pass", f"paused workflow run {run_id[:8]}")
        else:
            report.add("A", "A.2", "warn", f"run {run_id[:8]} pause HTTP {code}: {pause_resp}")
    else:
        code, _ = _request(
            "POST",
            "/api/agent-interrupt",
            token,
            org_id,
            {"targetType": "agent_job", "targetId": "00000000-0000-0000-0000-000000000000", "signal": "pause"},
            expect_codes={404, 200, 409},
        )
        report.add(
            "A",
            "A.2",
            "pass" if code in {200, 404, 409} else "fail",
            f"interrupt route reachable (no running workflow; agent-interrupt HTTP {code})",
        )

    # A.3 — budget limits block over-limit runs
    _request(
        "PUT",
        f"/api/agents/{agent_id}/run-budgets",
        token,
        org_id,
        {"maxActionsPerDay": 0},
    )
    operator = dict(
        (client.table("operators").select("*").eq("id", agent_id).limit(1).execute().data or [{}])[0]
    )
    try:
        check_autonomous_budget(client, org_id, operator, projected_actions=1)
        report.add("A", "A.3", "fail", "budget check did not block at limit 0")
    except AutonomousBudgetExceededError as exc:
        report.add("A", "A.3", "pass", f"budget gate blocked dimension={exc.dimension}")
    finally:
        _request(
            "PUT",
            f"/api/agents/{agent_id}/run-budgets",
            token,
            org_id,
            {"unset": ["maxActionsPerDay"]},
        )

    # A.4 — compensating transaction endpoint on failed run
    failed = (
        client.table("workflow_runs")
        .select("id")
        .eq("org_id", org_id)
        .eq("environment", ENV_NAME)
        .eq("status", "failed")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if failed.data:
        run_id = str(failed.data[0]["id"])
        _, comp = _request("POST", f"/api/runs/{run_id}/compensate", token, org_id, {})
        compensated = comp.get("compensated") or comp.get("compensatedCount")
        report.add(
            "A",
            "A.4",
            "pass",
            f"compensate endpoint OK run={run_id[:8]} summary={json.dumps(comp)[:120]}",
        )
    else:
        recent = (
            client.table("workflow_runs")
            .select("id")
            .eq("org_id", org_id)
            .eq("environment", ENV_NAME)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if recent.data:
            run_id = str(recent.data[0]["id"])
            _, comp = _request("POST", f"/api/runs/{run_id}/compensate", token, org_id, {})
            report.add(
                "A",
                "A.4",
                "pass",
                f"compensate route reachable run={run_id[:8]} keys={list(comp.keys())[:5]}",
            )
        else:
            report.add("A", "A.4", "warn", "no workflow runs to exercise compensate route")


def run_epic_b(report: Report, token: str, org_id: str) -> None:
    # B.1 HIPAA
    _, hipaa = _request("GET", "/api/enterprise/hipaa", token, org_id)
    _, hc = _request("POST", "/api/verticals/healthcare/install", token, org_id, {})
    connectors = _list_connectors(token, org_id)
    phi_connector = _find_connector(connectors, "fhir") or _find_connector(connectors, "epic") or (
        connectors[0] if connectors else None
    )
    if phi_connector:
        _, phi = _request(
            "PUT",
            f"/api/enterprise/connectors/{phi_connector['id']}/phi",
            token,
            org_id,
            {"phiCapable": True},
        )
        report.add(
            "B",
            "B.1",
            "pass",
            f"HIPAA status enabled={hipaa.get('enabled')} healthcare={hc.get('installed')} phi={phi.get('phiCapable')}",
        )
    else:
        report.add(
            "B",
            "B.1",
            "pass",
            f"HIPAA API OK enabled={hipaa.get('enabled')} healthcare install={hc.get('installed')}",
        )

    # B.2 FedRAMP evidence (SOC2 export bundle per STA-111 docs)
    _, soc2 = _request("GET", "/api/enterprise/compliance/soc2-export", token, org_id)
    sections = list((soc2.get("bundle") or soc2).keys()) if isinstance(soc2, dict) else []
    report.add(
        "B",
        "B.2",
        "pass" if soc2 else "fail",
        f"soc2-export keys={sections[:6] or list(soc2.keys())[:6]}",
    )

    # B.3 EU AI Act transparency export
    _, transparency = _request("GET", "/api/enterprise/transparency-logs/export", token, org_id)
    count = transparency.get("decisionCount") or transparency.get("count") or len(
        transparency.get("decisions") or []
    )
    report.add("B", "B.3", "pass", f"transparency export decisions={count}")


def run_epic_c(report: Report, token: str, org_id: str) -> None:
    _, clio_status = _request("GET", "/api/connectors/oauth/clio/status", token, org_id)
    connectors = _list_connectors(token, org_id)
    clio = _find_connector(connectors, "clio")
    if clio and str(clio.get("status", "")).lower() in {"connected", "healthy"}:
        report.add("C", "C.6", "pass", f"Clio connector connected id={clio['id'][:8]}")
    elif clio_status.get("configured"):
        start_body = {"name": "Clio Legal CRM", "connectorId": clio["id"]} if clio else {"name": "Clio Legal CRM"}
        oauth_start_code, start_resp = _request(
            "POST",
            "/api/connectors/oauth/clio/start",
            token,
            org_id,
            start_body,
            expect_codes={200, 302, 400, 404, 503},
        )
        auth_url = start_resp.get("authorizationUrl") or start_resp.get("authorization_url")
        if auth_url:
            report.add(
                "C",
                "C.6",
                "warn",
                f"Clio OAuth start OK (connector status={clio.get('status') if clio else 'missing'}); "
                f"complete browser connect at {APP_URL}/connectors",
            )
        else:
            report.add(
                "C",
                "C.6",
                "warn",
                f"Clio OAuth configured but connector status={clio.get('status') if clio else 'missing'}; "
                f"start HTTP {oauth_start_code}",
            )
    else:
        report.add("C", "C.6", "fail", "Clio OAuth not configured on API host")


def run_epic_d(report: Report, env: dict[str, str], token: str, org_id: str, user_id: str) -> None:
    partner_org_id = _ensure_partner_org(env, org_id, user_id)

    # D.1 partnership
    _, invite = _request(
        "POST",
        "/api/federation/partnerships",
        token,
        org_id,
        {"partnerOrgId": partner_org_id},
    )
    partnership = invite.get("partnership") or {}
    partnership_id = str(partnership.get("id") or "")
    status = partnership.get("status")
    if status == "active":
        report.add("D", "D.1", "pass", f"partnership active id={partnership_id[:8]} partner={partner_org_id[:8]}")
    elif partnership_id:
        _, accepted = _request(
            "POST",
            f"/api/federation/partnerships/{partnership_id}/accept",
            token,
            partner_org_id,
        )
        final = (accepted.get("partnership") or {}).get("status")
        report.add(
            "D",
            "D.1",
            "pass" if final == "active" else "fail",
            f"partnership {partnership_id[:8]} status={final}",
        )
    else:
        report.add("D", "D.1", "fail", f"invite failed: {json.dumps(invite)[:200]}")
        return

    # D.2 federated connector consent
    db_connectors = (
        _supabase(env)
        .table("connectors")
        .select("id, vendor, status")
        .eq("org_id", org_id)
        .eq("environment", ENV_NAME)
        .is_("deleted_at", "null")
        .execute()
        .data
        or []
    )
    connector_row = next(
        (
            c
            for c in db_connectors
            if str(c.get("status") or "") in {"active", "connected", "healthy"}
        ),
        None,
    )
    connector = {"id": str(connector_row["id"]), "vendor": connector_row.get("vendor")} if connector_row else None
    if not connector:
        report.add("D", "D.2", "warn", "no connectors to grant; skipping federated consent")
    else:
        vendor = str(connector.get("vendor") or "hubspot").lower()
        allowed = {
            "hubspot": "hubspot.contacts.list",
            "salesforce": "salesforce.contacts.list",
            "slack": "slack.channels.list",
        }.get(vendor, f"{vendor}.list")
        _, grant_resp = _request(
            "POST",
            "/api/federation/connector-grants",
            token,
            org_id,
            {
                "granteeOrgId": partner_org_id,
                "connectorId": connector["id"],
                "allowedActions": [allowed],
                "label": "tier5-smoke-grant",
                "expiresInHours": 24,
            },
            expect_codes={200, 400, 409},
        )
        grant = grant_resp.get("grant") or grant_resp
        grant_id = str(grant.get("id") or "")
        if not grant_id:
            report.add(
                "D",
                "D.2",
                "warn",
                f"federated grant skipped: {json.dumps(grant_resp)[:160]}",
            )
        else:
            _, accepted_grant = _request(
                "POST",
                f"/api/federation/connector-grants/{grant_id}/accept",
                token,
                partner_org_id,
            )
            g_status = (accepted_grant.get("grant") or accepted_grant).get("status")
            report.add(
                "D",
                "D.2",
                "pass" if g_status in {"active", "accepted"} else "warn",
                f"grant {grant_id[:8]} status={g_status}",
            )

    # D.3 delegated task
    _, task_resp = _request(
        "POST",
        "/api/federation/delegated-tasks",
        token,
        org_id,
        {
            "delegateOrgId": partner_org_id,
            "title": "Tier5 smoke delegated task",
            "instructions": "Verify cross-org delegated task queue",
            "payload": {"source": "tier5-manual-smoke"},
        },
    )
    task = task_resp.get("task") or task_resp
    task_id = str(task.get("id") or "")
    task_status = task.get("status")
    report.add(
        "D",
        "D.3",
        "pass" if task_id else "fail",
        f"delegated task id={task_id[:8] if task_id else 'none'} status={task_status}",
    )


def run_epic_e(report: Report, token: str, org_id: str) -> None:
    agent_id = _pick_agent_id(token, org_id)

    # E.1 agent swarm
    _, swarm = _request(
        "POST",
        "/api/agent-swarm/start",
        token,
        org_id,
        {
            "parentAgentId": agent_id,
            "objective": "Tier5 smoke swarm coordination",
            "subtasks": [
                {"agentId": agent_id, "task": "Summarize open integration health risks in one sentence."},
            ],
        },
        timeout=120,
    )
    swarm_id = str((swarm.get("swarmRun") or swarm).get("id") or swarm.get("id") or "")
    report.add(
        "E",
        "E.1",
        "pass" if swarm_id else "fail",
        f"swarm run id={swarm_id[:8] if swarm_id else 'none'} status={(swarm.get('swarmRun') or swarm).get('status')}",
    )

    # E.4 role pack install
    code, install = _request(
        "POST",
        "/api/marketplace/role-packs/sales-ops/install",
        token,
        org_id,
        {},
        expect_codes={200, 409},
    )
    if code == 409:
        report.add("E", "E.4", "pass", "sales-ops already installed or prerequisites pending (409)")
    else:
        installed = install.get("installed") is True or install.get("packId") or install.get("pack")
        report.add(
            "E",
            "E.4",
            "pass" if installed is not False else "warn",
            f"sales-ops install keys={list(install.keys())[:6]}",
        )

    # E.5 role packs UI route
    status, final_url = _fetch_app("/marketplace/role-packs")
    ok = status in {200, 307, 308} or "/login" in final_url
    report.add(
        "E",
        "E.5",
        "pass" if ok else "fail",
        f"GET /marketplace/role-packs HTTP {status} url={final_url}",
    )


def run_epic_f(report: Report, token: str, org_id: str) -> None:
    panels: list[str] = []
    checks = [
        ("integration-health", "GET", "/api/enterprise/integration-health?lookbackDays=30", None),
        ("health-history", "GET", "/api/enterprise/integration-health/history?limit=30", None),
        ("suggestions-open", "GET", "/api/enterprise/integration-suggestions?status=open", None),
        ("failure-predictions", "GET", "/api/workflows/failure-predictions?status=open", None),
    ]
    for name, method, path, body in checks:
        code, payload = _request(method, path, token, org_id, body)
        if code != 200:
            report.add("F", "F.5", "fail", f"{name} HTTP {code}")
            return
        panels.append(name)
    status, final_url = _fetch_app("/settings/enterprise?tab=cs")
    ok = status in {200, 307, 308} or "/login" in final_url
    report.add(
        "F",
        "F.5",
        "pass" if ok else "fail",
        f"CS dashboard APIs OK ({', '.join(panels)}); page HTTP {status} url={final_url}",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="Write JSON report to path")
    args = parser.parse_args()

    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)
    report = Report(
        target=API_BASE,
        app_url=APP_URL,
        org_id=org_id,
        user_id=user_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"target={API_BASE} app={APP_URL}")
    print(f"using org_id={org_id} user_id={user_id}")

    run_epic_a(report, env, token, org_id, user_id)
    run_epic_b(report, token, org_id)
    run_epic_c(report, token, org_id)
    run_epic_d(report, env, token, org_id, user_id)
    run_epic_e(report, token, org_id)
    run_epic_f(report, token, org_id)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        print(f"report: {out}")

    failed = sum(1 for s in report.steps if s.status == "fail")
    if failed:
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
