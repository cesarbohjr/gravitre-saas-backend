"""Production smoke: unified marketplace assets browse API (STA-229 / STA-239).

Usage:
  npm run smoke:marketplace-production
  python scripts/smoke-marketplace-production.py --json docs/delivery/smoke-marketplace-production-latest.json
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
API_BASE = os.environ.get(
    "BACKEND_URL",
    "https://api.gravitre.app",
).rstrip("/")
SMOKE_PAID_SLUG = "smoke-paid-operator-pack"
MIN_CATALOG_ASSETS = 50


@dataclass
class StepResult:
    label: str
    status: str  # pass | warn | fail
    detail: str = ""


@dataclass
class SmokeReport:
    target: str
    org_id: str
    started_at: str
    finished_at: str = ""
    catalog_total: int | None = None
    steps: list[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.status != "fail" for step in self.steps)


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (REPO / "backend" / ".env", REPO / "backend" / ".env.operator.local"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(path, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    # CI secrets land in process env only — must win over empty local files.
    merged.update({k: v for k, v in os.environ.items() if v})
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
    url = f"{API_BASE}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "X-Environment": "production",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _admin_context(env: dict[str, str]) -> tuple[str, str, str]:
    from supabase import create_client

    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET"):
        if env.get(key) and not os.environ.get(key):
            os.environ[key] = env[key]

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
    token = _mint_token(env, user_id, email)
    return org_id, user_id, token


def run_smoke(report: SmokeReport, token: str, org_id: str, client) -> None:
    assets = _request("/api/marketplace/assets?limit=5&environment=production", token, org_id)
    asset_list = assets.get("assets") or []
    total = int(assets.get("total") or 0)
    report.catalog_total = total
    detail = f"{len(asset_list)} returned, total={total}"
    if total < MIN_CATALOG_ASSETS:
        report.steps.append(
            StepResult(
                "catalog_assets",
                "fail",
                f"{detail}; expected ≥{MIN_CATALOG_ASSETS} (STA-229)",
            )
        )
    else:
        report.steps.append(StepResult("catalog_assets", "pass", detail))

    categories = _request("/api/marketplace/categories?environment=production", token, org_id)
    cat_count = len(categories.get("categories") or [])
    report.steps.append(StepResult("categories", "pass", f"count={cat_count}"))

    summary = _request("/api/marketplace/analytics/summary?environment=production", token, org_id)
    report.steps.append(
        StepResult("analytics_summary", "pass", f"keys={len(summary.keys())}")
    )

    roi = _request("/api/marketplace/analytics/roi?limit=5&environment=production", token, org_id)
    report.steps.append(
        StepResult(
            "analytics_roi",
            "pass",
            f"installs={roi.get('activeInstalls')} hours={roi.get('totalRealizedHoursSaved')}",
        )
    )

    federated = _request(
        "/api/marketplace/federated-connectors?limit=5&environment=production",
        token,
        org_id,
    )
    report.steps.append(StepResult("federated_connectors", "pass", f"total={federated.get('total')}"))

    billing = _request("/api/marketplace/billing/status?environment=production", token, org_id)
    asset_payouts = billing.get("assetPayouts") or {}
    report.steps.append(
        StepResult(
            "billing_status",
            "pass",
            f"connect={(billing.get('account') or {}).get('connectStatus')} "
            f"payouts={asset_payouts.get('payoutCount', 0)}",
        )
    )

    publisher_analytics = _request(
        "/api/marketplace/publisher/analytics?environment=production",
        token,
        org_id,
    )
    combined = (publisher_analytics.get("earnings") or {}).get("combined") or {}
    report.steps.append(
        StepResult(
            "publisher_analytics",
            "pass",
            f"grossCents={combined.get('grossCents')} "
            f"topAssets={len(publisher_analytics.get('topAssetsByEarnings') or [])}",
        )
    )

    slug = asset_list[0].get("slug") if asset_list else None
    if slug:
        detail_resp = _request(f"/api/marketplace/assets/{slug}?environment=production", token, org_id)
        title = (detail_resp.get("asset") or {}).get("title")
        report.steps.append(StepResult("asset_detail", "pass", f"{slug} -> {title}"))

        entitlement = _request(f"/api/marketplace/assets/{slug}/entitlement", token, org_id)
        report.steps.append(
            StepResult(
                "asset_entitlement",
                "pass",
                f"requiresPayment={entitlement.get('requiresPayment')} "
                f"hasEntitlement={entitlement.get('hasEntitlement')}",
            )
        )

        install_check = _request(
            f"/api/marketplace/assets/{slug}/install-check?environment=production",
            token,
            org_id,
        )
        report.steps.append(
            StepResult(
                "install_check",
                "pass",
                f"canInstall={install_check.get('canInstall')} "
                f"requiresPayment={install_check.get('requiresPayment')}",
            )
        )
    else:
        report.steps.append(StepResult("asset_detail", "warn", "no assets returned for detail checks"))

    paid = (
        client.table("marketplace_assets")
        .select("slug")
        .eq("slug", SMOKE_PAID_SLUG)
        .limit(1)
        .execute()
    )
    if paid.data:
        paid_slug = paid.data[0]["slug"]
        paid_ent = _request(f"/api/marketplace/assets/{paid_slug}/entitlement", token, org_id)
        report.steps.append(
            StepResult(
                "paid_asset_entitlement",
                "pass",
                f"requiresPayment={paid_ent.get('requiresPayment')} priceCents={paid_ent.get('priceCents')}",
            )
        )
    else:
        report.steps.append(
            StepResult(
                "paid_asset_entitlement",
                "warn",
                "run scripts/ensure_marketplace_smoke_paid_asset.py for paid-path smoke",
            )
        )

    verify_internal_visibility(report, token, org_id, client)


def verify_internal_visibility(
    report: SmokeReport,
    token: str,
    org_id: str,
    client,
) -> None:
    """STA-230 / MKT-AUDIT-5.4: internal assets scoped to owning org only."""
    other_internal = (
        client.table("marketplace_assets")
        .select("slug,org_id,visibility")
        .eq("visibility", "internal")
        .eq("status", "published")
        .neq("org_id", org_id)
        .limit(1)
        .execute()
    )
    other_row = (other_internal.data or [None])[0]

    public_resp = _request(
        "/api/marketplace/assets?visibility=public&limit=100&environment=production",
        token,
        org_id,
    )
    public_assets = public_resp.get("assets") or []
    bad_public = [a for a in public_assets if a.get("visibility") == "internal"]
    if bad_public:
        report.steps.append(
            StepResult(
                "visibility_public_filter",
                "fail",
                f"{len(bad_public)} internal assets in public browse",
            )
        )
    else:
        report.steps.append(
            StepResult(
                "visibility_public_filter",
                "pass",
                f"count={len(public_assets)} all public",
            )
        )

    internal_resp = _request(
        "/api/marketplace/assets?visibility=internal&limit=100&environment=production",
        token,
        org_id,
    )
    internal_assets = internal_resp.get("assets") or []
    bad_internal = [
        a
        for a in internal_assets
        if a.get("visibility") != "internal"
        or (a.get("orgId") and a.get("orgId") != org_id)
    ]
    if bad_internal:
        report.steps.append(
            StepResult(
                "visibility_internal_filter",
                "fail",
                f"{len(bad_internal)} out-of-scope assets",
            )
        )
    else:
        report.steps.append(
            StepResult(
                "visibility_internal_filter",
                "pass",
                f"count={len(internal_assets)} org-scoped",
            )
        )

    default_resp = _request(
        "/api/marketplace/assets?limit=100&environment=production",
        token,
        org_id,
    )
    default_assets = default_resp.get("assets") or []
    bad_default = [
        a
        for a in default_assets
        if a.get("visibility") == "internal"
        and a.get("orgId")
        and a.get("orgId") != org_id
    ]
    if bad_default:
        report.steps.append(
            StepResult(
                "visibility_default_browse",
                "fail",
                f"{len(bad_default)} leaked internal assets",
            )
        )
    elif other_row:
        other_slug = other_row["slug"]
        slugs = {a.get("slug") for a in default_assets}
        if other_slug in slugs:
            report.steps.append(
                StepResult(
                    "visibility_default_browse",
                    "fail",
                    f"other-org internal {other_slug} in default browse",
                )
            )
        else:
            report.steps.append(
                StepResult(
                    "visibility_default_browse",
                    "pass",
                    f"other-org internal {other_slug} hidden",
                )
            )
    else:
        report.steps.append(
            StepResult(
                "visibility_default_browse",
                "warn",
                "no other-org internal asset to cross-check",
            )
        )

    if other_row:
        other_slug = other_row["slug"]
        try:
            _request(
                f"/api/marketplace/assets/{other_slug}?environment=production",
                token,
                org_id,
            )
            report.steps.append(
                StepResult(
                    "visibility_detail_block",
                    "fail",
                    f"{other_slug} accessible cross-org",
                )
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                report.steps.append(
                    StepResult(
                        "visibility_detail_block",
                        "pass",
                        f"{other_slug} returns 404",
                    )
                )
            else:
                report.steps.append(
                    StepResult(
                        "visibility_detail_block",
                        "fail",
                        f"HTTP {exc.code}",
                    )
                )
    else:
        report.steps.append(
            StepResult(
                "visibility_detail_block",
                "warn",
                "no other-org internal asset for detail check",
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Marketplace production smoke (STA-229 / STA-239)")
    parser.add_argument("--json", dest="json_path", help="Write structured report JSON")
    args = parser.parse_args()

    env = _load_env()
    report = SmokeReport(
        target=API_BASE,
        org_id="",
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        from supabase import create_client

        org_id, _user_id, token = _admin_context(env)
        report.org_id = org_id
        print(f"using org_id={org_id}")

        client = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
        run_smoke(report, token, org_id, client)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        report.steps.append(StepResult("http_error", "fail", f"HTTP {exc.code}: {body[:240]}"))
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
        payload["min_catalog_assets"] = MIN_CATALOG_ASSETS
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")

    if report.ok:
        print("OK")
        return 0
    print("FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
