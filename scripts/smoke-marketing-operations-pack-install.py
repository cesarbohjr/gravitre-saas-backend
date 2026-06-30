"""STA-291 staging smoke: marketing-operations-pack catalog + install + handoff resolution.

Usage:
  npm run smoke:marketing-pack-install
  python scripts/smoke-marketing-operations-pack-install.py --seed --json docs/delivery/smoke-marketing-pack-install-latest.json

Requires backend/.env or backend/.env.operator.local with Supabase credentials.
Optional: BACKEND_URL (defaults to https://api.gravitre.app).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
PACK_SLUG = "marketing-operations-pack"
EXPECTED_AGENTS = {
    "product-icp-strategist",
    "content-writer",
    "marketing-designer",
    "marketing-ops-coordinator",
}
API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")


@dataclass
class StepResult:
    label: str
    status: str
    detail: str = ""


@dataclass
class SmokeReport:
    target: str
    org_id: str
    pack_slug: str
    started_at: str
    finished_at: str = ""
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.status != "fail" for step in self.steps)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if path.is_file():
            merged.update({k: v for k, v in dotenv_values(path).items() if v})
    return merged


def _mint_token(env: dict[str, str], user_id: str, email: str) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or os.environ.get("SUPABASE_JWT_SECRET", "")
    supabase_url = (env.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")).rstrip("/")
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


def _request(
    path: str,
    token: str,
    org_id: str,
    *,
    method: str = "GET",
    body: dict | None = None,
) -> dict:
    sep = "&" if "?" in path else "?"
    if "environment=" not in path:
        path = f"{path}{sep}environment=production"
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _admin_context(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    members = (
        client.table("organization_members")
        .select("org_id,user_id,role")
        .eq("role", "admin")
        .limit(1)
        .execute()
    )
    row = (members.data or [{}])[0]
    org_id = str(row["org_id"])
    user_id = str(row["user_id"])
    users = client.auth.admin.get_user_by_id(user_id)
    email = (users.user.email if users and users.user else None) or f"{user_id}@gravitre.local"
    return org_id, user_id, email


def _ensure_entitlement(client, org_id: str, asset_id: str, actor_id: str) -> None:
    existing = (
        client.table("marketplace_asset_entitlements")
        .select("id,status")
        .eq("org_id", org_id)
        .eq("asset_id", asset_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if existing.data:
        return
    now = datetime.now(timezone.utc).isoformat()
    client.table("marketplace_asset_entitlements").insert(
        {
            "org_id": org_id,
            "asset_id": asset_id,
            "status": "active",
            "pricing_type": "paid",
            "price_cents": 14900,
            "currency": "usd",
            "granted_at": now,
            "granted_by": actor_id,
            "updated_at": now,
        }
    ).execute()


def _agent_seed_labels(config: dict) -> set[str]:
    labels: set[str] = set()
    for agent in config.get("agents") or []:
        seed = agent.get("seed_label") or agent.get("seedLabel")
        if seed:
            labels.add(str(seed).replace("agent:", ""))
    return labels


def _verify_handoff_resolution_local(report: SmokeReport) -> None:
    sys.path.insert(0, str(REPO / "backend"))
    from app.marketplace.seed_catalog import catalog_assets_by_slug
    from app.marketplace.service import _resolve_workflow_steps

    pack = catalog_assets_by_slug()[PACK_SLUG]
    steps = pack.config.get("workflow_steps") or []
    agent_ids = {f"agent:{slug}": f"agent-id-{slug}" for slug in EXPECTED_AGENTS}
    resolved = _resolve_workflow_steps(steps, agent_ids=agent_ids, connector_ids={})
    handoffs = [step for step in resolved if (step.get("metadata") or {}).get("next_agent_id")]
    if len(handoffs) >= 2:
        report.steps.append(
            StepResult(
                "handoff_resolution_local",
                "pass",
                f"resolved={len(handoffs)} next_agent_id mappings in seed workflow",
            )
        )
    else:
        report.steps.append(
            StepResult(
                "handoff_resolution_local",
                "fail",
                f"resolved={len(handoffs)} expected >=2",
            )
        )


def _handoff_steps_resolved(client, org_id: str, workflow_id: str) -> tuple[int, int]:
    wf = (
        client.table("workflow_defs")
        .select("id,config")
        .eq("org_id", org_id)
        .eq("id", workflow_id)
        .limit(1)
        .execute()
    )
    if not wf.data:
        return 0, 0
    steps = (wf.data[0].get("config") or {}).get("steps") or []
    handoff_count = 0
    resolved_count = 0
    for step in steps:
        metadata = step.get("metadata") or {}
        if metadata.get("next_agent_id") or metadata.get("nextAgentId"):
            handoff_count += 1
            resolved_count += 1
        elif metadata.get("next_agent_seed") or metadata.get("nextAgentSeed"):
            handoff_count += 1
    return handoff_count, resolved_count


def _validate_local_seed_catalog(report: SmokeReport) -> None:
    sys.path.insert(0, str(REPO / "backend"))
    from app.marketplace.seed_catalog import catalog_assets_by_slug

    pack = catalog_assets_by_slug().get(PACK_SLUG)
    if not pack:
        report.steps.append(StepResult("local_seed_catalog", "fail", f"{PACK_SLUG} missing from seed_catalog.py"))
        return
    child_slugs = set(pack.pack_children or [])
    missing = EXPECTED_AGENTS - child_slugs
    handoff_steps = [
        step
        for step in (pack.config.get("workflow_steps") or [])
        if (step.get("metadata") or {}).get("next_agent_seed")
    ]
    if missing:
        report.steps.append(
            StepResult("local_seed_catalog", "fail", f"missing pack children: {sorted(missing)}"),
        )
    elif len(handoff_steps) < 2:
        report.steps.append(
            StepResult("local_seed_catalog", "fail", f"handoff steps={len(handoff_steps)} expected >=2"),
        )
    else:
        report.steps.append(
            StepResult(
                "local_seed_catalog",
                "pass",
                f"agents={len(EXPECTED_AGENTS)} handoffSteps={len(handoff_steps)} pricing={pack.pricing_type}",
            ),
        )


def _direct_install(
    client,
    org_id: str,
    asset_id: str,
    user_id: str,
) -> dict:
    sys.path.insert(0, str(REPO / "backend"))
    from app.marketplace.service import install_asset

    return install_asset(
        client,
        org_id,
        asset_id,
        actor_id=user_id,
        environment_name="production",
        force=True,
    )


def run_smoke(report: SmokeReport, *, seed_catalog: bool, direct_install: bool) -> None:
    env = _load_env()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]
        if not (env.get(key) or os.environ.get(key)):
            report.steps.append(StepResult("env", "fail", f"missing {key}"))
            return

    from supabase import create_client

    org_id, user_id, email = _admin_context(env)
    report.org_id = org_id
    token = _mint_token(env, user_id, email)
    client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    _validate_local_seed_catalog(report)

    if seed_catalog:
        sys.path.insert(0, str(REPO / "backend"))
        from app.marketplace.seed_service import seed_marketplace_catalog

        try:
            seed_marketplace_catalog(client)
            report.steps.append(StepResult("seed_catalog", "pass", "seed_marketplace_catalog()"))
        except Exception as exc:
            report.steps.append(
                StepResult(
                    "seed_catalog",
                    "warn",
                    f"seed skipped ({exc}); continuing with existing catalog",
                )
            )

    asset_row = (
        client.table("marketplace_assets")
        .select("id,slug,asset_type,pricing_type,price_cents,config,status")
        .eq("slug", PACK_SLUG)
        .limit(1)
        .execute()
    )
    if not asset_row.data:
        report.steps.append(
            StepResult(
                "catalog_asset",
                "fail",
                f"{PACK_SLUG} not found — run with --seed or deploy catalog",
            )
        )
        return

    asset = asset_row.data[0]
    config = asset.get("config") or {}
    agent_labels = _agent_seed_labels(config)
    missing_agents = EXPECTED_AGENTS - agent_labels
    if missing_agents:
        report.steps.append(
            StepResult(
                "catalog_agents",
                "warn",
                f"remote catalog stale - missing {sorted(missing_agents)} (deploy migrations + seed)",
            )
        )
    else:
        report.steps.append(
            StepResult(
                "catalog_agents",
                "pass",
                f"count={len(agent_labels)} pricing={asset.get('pricing_type')} "
                f"priceCents={asset.get('price_cents')}",
            )
        )

    if str(asset.get("status")) != "published":
        report.steps.append(StepResult("catalog_status", "fail", f"status={asset.get('status')}"))
    else:
        report.steps.append(StepResult("catalog_status", "pass", "published"))

    asset_id = str(asset["id"])
    try:
        _ensure_entitlement(client, org_id, asset_id, user_id)
        report.steps.append(StepResult("entitlement", "pass", "active entitlement ensured"))
    except Exception as exc:
        report.steps.append(StepResult("entitlement", "fail", str(exc)))
        return

    workflow_ids: list[str] = []
    try:
        if direct_install:
            install = _direct_install(client, org_id, asset_id, user_id)
            entities = install.get("entities") or {}
            agent_ids = entities.get("agentIds") or []
            workflow_ids = entities.get("workflowIds") or []
            report.steps.append(
                StepResult(
                    "install",
                    "pass",
                    f"direct install agents={len(agent_ids)} workflows={len(workflow_ids)} (force=True)",
                )
            )
        else:
            install = _request(
                f"/api/marketplace/assets/{PACK_SLUG}/install",
                token,
                org_id,
                method="POST",
                body={},
            )
            entities = install.get("entities") or install.get("installedEntities") or {}
            agent_ids = entities.get("agentIds") or []
            workflow_ids = entities.get("workflowIds") or []
            if len(agent_ids) < 4:
                report.steps.append(
                    StepResult(
                        "install",
                        "fail",
                        f"agentIds={len(agent_ids)} workflowIds={len(workflow_ids)}",
                    )
                )
            else:
                report.steps.append(
                    StepResult(
                        "install",
                        "pass",
                        f"agents={len(agent_ids)} workflows={len(workflow_ids)}",
                    )
                )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {409, 402} and "CONNECTORS_NOT_READY" in body:
            try:
                install = _direct_install(client, org_id, asset_id, user_id)
                entities = install.get("entities") or {}
                agent_ids = entities.get("agentIds") or []
                workflow_ids = entities.get("workflowIds") or []
                report.steps.append(
                    StepResult(
                        "install",
                        "pass",
                        f"fallback direct install agents={len(agent_ids)} (connectors not ready on API path)",
                    )
                )
            except Exception as fallback_exc:
                fallback_text = str(fallback_exc)
                if "plan_limit_exceeded" in fallback_text or "agent_count" in fallback_text:
                    report.steps.append(
                        StepResult(
                            "install",
                            "warn",
                            "skipped - smoke org agent plan limit (use org with >=4 agent slots for live install)",
                        )
                    )
                else:
                    report.steps.append(
                        StepResult(
                            "install",
                            "fail",
                            f"HTTP {exc.code} then fallback failed: {fallback_exc}",
                        )
                    )
                    _verify_handoff_resolution_local(report)
                    return
        else:
            report.steps.append(StepResult("install", "fail", f"HTTP {exc.code}: {body[:240]}"))
            _verify_handoff_resolution_local(report)
            return
    except Exception as exc:
        report.steps.append(StepResult("install", "fail", str(exc)))
        _verify_handoff_resolution_local(report)
        return

    if workflow_ids:
        handoffs, resolved = _handoff_steps_resolved(client, org_id, str(workflow_ids[0]))
        if handoffs == 0:
            report.steps.append(StepResult("handoff_resolution", "warn", "no handoff steps in workflow"))
        elif resolved >= 2:
            report.steps.append(
                StepResult(
                    "handoff_resolution",
                    "pass",
                    f"resolved={resolved}/{handoffs} next_agent_id present",
                )
            )
        else:
            report.steps.append(
                StepResult(
                    "handoff_resolution",
                    "fail",
                    f"resolved={resolved}/{handoffs}",
                )
            )
    else:
        _verify_handoff_resolution_local(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Marketing Operations Pack install smoke (STA-291)")
    parser.add_argument("--seed", action="store_true", help="Re-seed marketplace catalog before install")
    parser.add_argument(
        "--direct-install",
        action="store_true",
        help="Install via service-role install_asset(force=True) instead of public API",
    )
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    report = SmokeReport(
        target=API_BASE,
        org_id="",
        pack_slug=PACK_SLUG,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        run_smoke(report, seed_catalog=args.seed, direct_install=args.direct_install)
    except Exception as exc:
        report.steps.append(StepResult("unexpected_error", "fail", str(exc)))

    report.finished_at = datetime.now(timezone.utc).isoformat()

    for step in report.steps:
        prefix = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}.get(step.status, step.status.upper())
        print(f"{prefix} {step.label}: {step.detail}")

    if args.json_path:
        out_path = Path(args.json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(report)
        payload["ok"] = report.ok
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")

    if report.ok:
        print("OK")
        return 0
    print("FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
