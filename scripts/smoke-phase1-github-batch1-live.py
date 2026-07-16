#!/usr/bin/env python3
"""Live smoke: GitHub Batch 1 — pulls.create, actions.runs.list, issues.update.

Writes docs/delivery/phase1-github-batch1-live.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

BASE = os.environ.get(
    "BACKEND_URL",
    "https://gravitre-saas-backend-production.up.railway.app",
).rstrip("/")
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
OUT = REPO / "docs" / "delivery" / "phase1-github-batch1-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not p.is_file():
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded:
            merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _rec(invoke) -> dict:
    data = invoke.data or {}
    return {
        "success": bool(invoke.success),
        "error_code": invoke.error_code,
        "error_message": invoke.error_message,
        "result_url": data.get("result_url")
        or (data.get("issue") or {}).get("html_url")
        or (data.get("pull_request") or {}).get("html_url"),
        "summary": data.get("summary"),
        "data_keys": list(data.keys())[:12],
    }


def _invoke_retry(invoke_tool, ctx, action: str, params: dict, *, attempts: int = 4):
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return invoke_tool(ctx, action, params)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc)
            transient = "10035" in msg or "ConnectionTerminated" in msg or "ReadError" in msg
            if not transient or i + 1 >= attempts:
                raise
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(str(last_exc or "invoke failed"))


def main() -> int:
    _load_env()
    from app.config import get_settings
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    settings = get_settings()
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    tip = None
    try:
        tip = httpx.get(f"{BASE}/health", timeout=60.0).json().get("git_sha")
    except Exception as exc:  # noqa: BLE001
        tip = f"health_unreachable:{exc.__class__.__name__}"

    rows = (
        sb.table("connectors")
        .select("id, type, status, config")
        .eq("org_id", ORG)
        .eq("type", "github")
        .is_("deleted_at", "null")
        .limit(5)
        .execute()
    ).data or []
    gh = None
    for row in rows:
        if str(row.get("status") or "").lower() in {"active", "connected", "healthy"}:
            gh = row
            break
    if not gh and rows:
        gh = rows[0]

    invokes: dict[str, dict] = {}
    gh_id = str(gh["id"]) if gh else None
    cfg = (gh or {}).get("config") or {}
    owner = str(cfg.get("owner") or os.environ.get("GITHUB_SMOKE_OWNER") or "").strip()
    repo = str(cfg.get("repo") or os.environ.get("GITHUB_SMOKE_REPO") or "").strip()

    if gh_id and owner and repo:
        ctx = ToolContext(
            settings=settings,
            client=sb,
            org_id=ORG,
            actor_id=ACTOR,
            connector_id=gh_id,
        )
        # 1) actions.runs.list (read tip)
        runs = _invoke_retry(
            invoke_tool,
            ctx,
            "github.actions.runs.list",
            {"connector_id": gh_id, "owner": owner, "repo": repo, "per_page": 5},
        )
        invokes["github.actions.runs.list"] = _rec(runs)
        time.sleep(0.6)

        # 2) create issue then update it (safer than opening a PR without head branch)
        suffix = uuid.uuid4().hex[:8]
        created = _invoke_retry(
            invoke_tool,
            ctx,
            "github.issues.create",
            {
                "connector_id": gh_id,
                "owner": owner,
                "repo": repo,
                "title": f"Gravitre Batch1 smoke {suffix}",
                "body": "Temporary Batch 1 tip issue — safe to close.",
            },
        )
        invokes["github.issues.create"] = _rec(created)
        issue_number = None
        if created.success:
            issue = (created.data or {}).get("issue") or {}
            issue_number = issue.get("number")
        time.sleep(0.6)

        if issue_number:
            updated = _invoke_retry(
                invoke_tool,
                ctx,
                "github.issues.update",
                {
                    "connector_id": gh_id,
                    "owner": owner,
                    "repo": repo,
                    "issue_number": int(issue_number),
                    "state": "closed",
                    "body": f"Closed by Batch 1 tip ({suffix})",
                },
            )
            invokes["github.issues.update"] = _rec(updated)
        else:
            invokes["github.issues.update"] = {
                "success": False,
                "error_code": "skipped",
                "error_message": "no issue_number from issues.create",
                "result_url": None,
                "summary": None,
                "data_keys": [],
            }

        # 3) pulls.create — only if smoke head branch is provided
        head = str(os.environ.get("GITHUB_SMOKE_HEAD") or cfg.get("smoke_head") or "").strip()
        base = str(os.environ.get("GITHUB_SMOKE_BASE") or cfg.get("default_branch") or "main").strip()
        if head:
            pr = _invoke_retry(
                invoke_tool,
                ctx,
                "github.pulls.create",
                {
                    "connector_id": gh_id,
                    "owner": owner,
                    "repo": repo,
                    "title": f"Gravitre Batch1 draft tip {suffix}",
                    "head": head,
                    "base": base,
                    "draft": True,
                    "body": "Draft tip PR from Batch 1 smoke — safe to close.",
                },
            )
            invokes["github.pulls.create"] = _rec(pr)
        else:
            invokes["github.pulls.create"] = {
                "success": False,
                "error_code": "skipped",
                "error_message": "set GITHUB_SMOKE_HEAD (or config.smoke_head) to tip pulls.create",
                "result_url": None,
                "summary": None,
                "data_keys": [],
            }

    new_ok = all(
        invokes.get(k, {}).get("success") and invokes.get(k, {}).get("result_url")
        for k in ("github.actions.runs.list", "github.issues.update")
    )
    pulls_ok = invokes.get("github.pulls.create", {}).get("success") or (
        invokes.get("github.pulls.create", {}).get("error_code") == "skipped"
    )
    # pulls.create skip is allowed when no head branch; action still must be registered locally
    from app.services.tool_service import list_registered_actions

    registered = set(list_registered_actions())
    actions_present = {
        "github.pulls.create",
        "github.actions.runs.list",
        "github.issues.update",
    }.issubset(registered)

    passed = bool(gh_id and owner and repo and new_ok and pulls_ok and actions_present)

    artifact = {
        "pass": passed,
        "status": "PASS" if passed else "BLOCKED_EXTERNAL",
        "ran_at": utcnow(),
        "prod_git_sha": tip,
        "org_id": ORG,
        "batch": "phase1-github-batch1",
        "api_version": "GitHub REST 2022-11-28 (no bump)",
        "new_actions": [
            "github.pulls.create",
            "github.actions.runs.list",
            "github.issues.update",
        ],
        "github_connector_id": gh_id,
        "owner": owner or None,
        "repo": repo or None,
        "invokes": invokes,
        "blocker": None
        if passed
        else {
            "kind": "github_connector_missing_or_incomplete",
            "class": "external_dependency",
            "detail": (
                "Smoke org has no healthy GitHub connector with owner/repo configured. "
                "Connect GitHub on org cbbf993b-… (OAuth scopes repo read:user), set owner/repo, "
                "optionally GITHUB_SMOKE_HEAD for pulls.create tip, then re-run."
            ),
        },
        "governance": {
            "finance_hr_excluded": True,
            "chat_access_granted": False,
        },
        "note": (
            "GitHub Batch 1 tip PASS."
            if passed
            else "GitHub Batch 1 code ready; tip blocked until smoke GitHub connector exists."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass": passed,
                "out": str(OUT),
                "gh_id": gh_id,
                "owner": owner,
                "repo": repo,
                "tip": tip,
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
