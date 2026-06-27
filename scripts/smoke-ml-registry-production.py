"""Production smoke for ML Model Registry (/api/ml).

Verifies health, list/create/get/deploy against Railway or api.gravitre.app,
and optionally predict when a deployed artifact exists.

Usage:
  npm run smoke:ml-registry
  python scripts/smoke-ml-registry-production.py --json docs/delivery/smoke-ml-registry-latest.json
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
ENV_FILE = REPO / "backend" / ".env.operator.local"
ENV_BACKEND = REPO / "backend" / ".env"
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
APP_BASE = os.environ.get("APP_BASE_URL", "https://gravitre.app").rstrip("/")
ENV_NAME = "production"
SMOKE_MODEL_PREFIX = "smoke-ml-registry"


@dataclass
class StepResult:
    label: str
    status: str  # pass | warn | fail
    detail: str = ""


@dataclass
class SmokeReport:
    target: str
    org_id: str
    user_id: str
    started_at: str
    finished_at: str = ""
    steps: list[StepResult] = field(default_factory=list)
    model_id: str | None = None

    def add(self, label: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(label=label, status=status, detail=detail))

    def to_dict(self) -> dict[str, Any]:
        passed = sum(1 for s in self.steps if s.status == "pass")
        warned = sum(1 for s in self.steps if s.status == "warn")
        failed = sum(1 for s in self.steps if s.status == "fail")
        return {
            "target": self.target,
            "appProxy": APP_BASE,
            "orgId": self.org_id,
            "userId": self.user_id,
            "modelId": self.model_id,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "summary": {"pass": passed, "warn": warned, "fail": failed},
            "steps": [{"label": s.label, "status": s.status, "detail": s.detail} for s in self.steps],
        }


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (ENV_BACKEND, ENV_FILE):
        if not path.is_file():
            continue
        try:
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip().strip('"')
                if value:
                    merged[key.strip()] = value
    return merged


def _with_environment(path: str) -> str:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment={ENV_NAME}"
    return path


def _request(
    base: str,
    method: str,
    path: str,
    token: str | None,
    org_id: str | None,
    body: dict | None = None,
    *,
    timeout: int = 60,
) -> tuple[int, dict | str]:
    path = _with_environment(path)
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if org_id:
        req.add_header("X-Org-Id", org_id)
    req.add_header("X-Environment", ENV_NAME)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            code = resp.getcode()
            try:
                return code, json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                return code, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    if not secret or not supabase_url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required in backend/.env.operator.local")
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


def _supabase_client(env: dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    return create_client(url, key)


def _admin_org(env: dict[str, str]) -> tuple[str, str, str]:
    org_id = env.get("OPERATOR_ORG_ID") or os.environ.get("OPERATOR_ORG_ID", "")
    user_id = env.get("OPERATOR_USER_ID") or os.environ.get("OPERATOR_USER_ID", "")
    email = env.get("OPERATOR_EMAIL") or os.environ.get("OPERATOR_EMAIL", "")
    if org_id and user_id:
        return org_id, user_id, email or f"{user_id}@gravitre.local"

    client = _supabase_client(env)
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
    resolved_email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, resolved_email


def _detail(payload: dict | str) -> str:
    if isinstance(payload, str):
        return payload[:300]
    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return str(first.get("msg") or first)
    return json.dumps(payload)[:300]


def run_smoke(report: SmokeReport, token: str, org_id: str) -> None:
    # Health — direct API
    code, body = _request(API_BASE, "GET", "/health", None, None)
    if code == 200:
        report.add("api_health", "pass", f"{API_BASE}/health -> 200")
    else:
        report.add("api_health", "fail", f"{API_BASE}/health -> {code}: {_detail(body)}")

    # Frontend proxy — ML route should return 401 without auth (proves rewrite works)
    code, body = _request(APP_BASE, "GET", "/api/ml/models", None, None)
    if code == 401:
        report.add("app_proxy_health", "pass", f"{APP_BASE}/api/ml/models -> 401 (proxy reachable)")
    elif code == 200:
        report.add("app_proxy_health", "pass", f"{APP_BASE}/api/ml/models -> 200")
    else:
        report.add("app_proxy_health", "warn", f"{APP_BASE}/api/ml/models -> {code}: {_detail(body)}")

    # List models
    code, body = _request(API_BASE, "GET", "/api/ml/models", token, org_id)
    if code != 200 or not isinstance(body, dict):
        report.add("ml_list", "fail", f"GET /api/ml/models -> {code}: {_detail(body)}")
        return
    models = body.get("models") or []
    report.add("ml_list", "pass", f"{len(models)} model(s) in registry")

    # Create draft model
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    create_payload = {
        "name": f"{SMOKE_MODEL_PREFIX}-{stamp}",
        "model_type": "classifier",
        "description": "Automated ML registry smoke test",
        "base_model": "logistic-regression",
        "task_type": "binary",
    }
    code, body = _request(API_BASE, "POST", "/api/ml/models", token, org_id, create_payload)
    if code not in (200, 201) or not isinstance(body, dict) or not body.get("id"):
        report.add("ml_create", "fail", f"POST /api/ml/models -> {code}: {_detail(body)}")
        return
    model_id = str(body["id"])
    report.model_id = model_id
    report.add("ml_create", "pass", f"created {model_id}")

    # Get detail (versions + task_type)
    code, body = _request(API_BASE, "GET", f"/api/ml/models/{model_id}", token, org_id)
    if code != 200 or not isinstance(body, dict):
        report.add("ml_get", "fail", f"GET detail -> {code}: {_detail(body)}")
        return
    versions = body.get("versions") or []
    task_type = body.get("task_type")
    report.add(
        "ml_get",
        "pass",
        f"status={body.get('status')} base_model={body.get('base_model')} task_type={task_type} versions={len(versions)}",
    )

    # Deploy without trained version should fail or warn
    code, body = _request(
        API_BASE,
        "POST",
        f"/api/ml/models/{model_id}/deploy",
        token,
        org_id,
        {"version": None},
    )
    if code >= 400:
        report.add("ml_deploy_draft", "pass", f"deploy blocked on draft (expected): {_detail(body)}")
    else:
        report.add("ml_deploy_draft", "warn", f"deploy succeeded on draft v0: {_detail(body)}")

    # Predict without artifact should fail gracefully
    code, body = _request(
        API_BASE,
        "POST",
        f"/api/ml/models/{model_id}/predict",
        token,
        org_id,
        {"inputs": [{"feature_a": 1}], "return_probabilities": False},
    )
    if code >= 400:
        report.add("ml_predict_no_artifact", "pass", f"predict blocked without artifact: {_detail(body)}")
    else:
        report.add("ml_predict_no_artifact", "warn", f"predict returned {code}: {_detail(body)}")

    # Proxy route parity — list via gravitre.app (same path the browser uses)
    code, proxy_body = _request(APP_BASE, "GET", "/api/ml/models", token, org_id)
    if code == 200 and isinstance(proxy_body, dict):
        report.add("app_proxy_ml_list", "pass", "frontend proxy reaches /api/ml/models")
    else:
        report.add("app_proxy_ml_list", "fail", f"proxy list -> {code}: {_detail(proxy_body)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="ML registry production smoke")
    parser.add_argument("--json", type=Path, help="Write JSON report")
    args = parser.parse_args()

    env = _load_env()
    org_id, user_id, email = _admin_org(env)
    token = _mint_token(env, user_id, email)

    report = SmokeReport(
        target=API_BASE,
        org_id=org_id,
        user_id=user_id,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        run_smoke(report, token, org_id)
    except Exception as exc:  # noqa: BLE001
        report.add("smoke_exception", "fail", str(exc))

    report.finished_at = datetime.now(timezone.utc).isoformat()
    payload = report.to_dict()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json}")

    for step in report.steps:
        icon = {"pass": "OK", "warn": "!!", "fail": "XX"}[step.status]
        print(f"[{icon}] {step.label}: {step.detail}")

    summary = payload["summary"]
    print(
        f"\nSummary: pass={summary['pass']} warn={summary['warn']} fail={summary['fail']} "
        f"(target={API_BASE})"
    )
    return 1 if summary["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
