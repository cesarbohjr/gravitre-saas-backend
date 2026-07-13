"""Part D P5 live HTTP trace after Option A schema migration."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local"]:
    if p.is_file():
        for k, v in dotenv_values(p).items():
            if v:
                os.environ.setdefault(k, v)

sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings
from app.workflows.repository import get_supabase_client

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
OUT = ROOT / "docs" / "delivery" / "part-d-p5-live-trace.json"
COMBINED = ROOT / "docs" / "delivery" / "part-d-p4-p6-live-traces.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clear_agent_knowledge_assignments(client, agent_id: str) -> int:
    try:
        existing = (
            client.table("agent_knowledge_assignments")
            .select("id")
            .eq("org_id", ORG)
            .eq("agent_id", agent_id)
            .limit(100)
            .execute()
            .data
            or []
        )
        for row in existing:
            client.table("agent_knowledge_assignments").delete().eq("id", row["id"]).eq(
                "org_id", ORG
            ).execute()
        return len(existing)
    except Exception:  # noqa: BLE001
        return 0


def main() -> int:
    c = get_supabase_client(get_settings())
    pack = (
        c.table("marketplace_assets")
        .select("id,slug,asset_type")
        .eq("slug", "support-intelligence-pack")
        .limit(1)
        .execute()
        .data
        or [None]
    )[0]
    if not pack:
        raise SystemExit("support-intelligence-pack not seeded")

    probe_name = f"PartD-P5-Probe-{uuid.uuid4().hex[:6]}"
    created = (
        c.table("agents")
        .insert({"org_id": ORG, "name": probe_name, "status": "active", "config": {}})
        .execute()
    )
    agent_id = str((created.data or [{}])[0].get("id") or "")
    if not agent_id:
        raise SystemExit("failed to create probe agent")

    email = c.auth.admin.get_user_by_id(ACTOR).user.email
    url = os.environ["SUPABASE_URL"].rstrip("/")
    tok = jwt.encode(
        {
            "sub": ACTOR,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }

    since = utcnow()
    with httpx.Client(verify=False, timeout=120) as http:
        # Hygiene: clear any prior active install + stale assignments before fresh install.
        pre_uninstall = http.post(
            f"{BASE}/api/marketplace/assets/{pack['id']}/uninstall",
            headers=hdr,
        )
        cleared = _clear_agent_knowledge_assignments(c, agent_id)
        time.sleep(0.5)

        install = http.post(
            f"{BASE}/api/marketplace/assets/{pack['id']}/install",
            headers=hdr,
            json={"installVariables": {"agentId": agent_id}},
        )
        body = install.json() if install.content else {}
        if install.status_code == 409 and "already exists" in str(
            (body or {}).get("error") or (body or {}).get("detail") or ""
        ).lower():
            _clear_agent_knowledge_assignments(c, agent_id)
            http.post(f"{BASE}/api/marketplace/assets/{pack['id']}/uninstall", headers=hdr)
            time.sleep(0.5)
            install = http.post(
                f"{BASE}/api/marketplace/assets/{pack['id']}/install",
                headers=hdr,
                json={"installVariables": {"agentId": agent_id}},
            )
            body = install.json() if install.content else {}

        time.sleep(1.0)
        audits = (
            c.table("audit_events")
            .select("action,metadata,created_at,resource_type,resource_id")
            .eq("org_id", ORG)
            .gte("created_at", since)
            .in_(
                "action",
                ["marketplace.intelligence_pack.installed", "marketplace.asset.installed"],
            )
            .order("created_at", desc=True)
            .limit(10)
            .execute()
            .data
            or []
        )
        install_row = (
            c.table("marketplace_installs")
            .select("id,status,installed_entity_type,installed_entity_id,metadata")
            .eq("org_id", ORG)
            .eq("asset_id", pack["id"])
            .eq("status", "active")
            .order("installed_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        ok = (
            install.status_code in {200, 201}
            and isinstance(body, dict)
            and (
                body.get("installed") is True
                or body.get("assetType") == "intelligence_pack"
                or (install_row and install_row[0].get("installed_entity_type") == "intelligence_pack")
            )
            and bool(audits)
        )
        # cleanup
        uninstall = http.post(
            f"{BASE}/api/marketplace/assets/{pack['id']}/uninstall",
            headers=hdr,
            timeout=60,
        )
    try:
        c.table("agents").delete().eq("id", agent_id).eq("org_id", ORG).execute()
    except Exception:
        pass

    report = {
        "ticket": "STA-310",
        "ran_at": utcnow(),
        "option_a_applied": True,
        "prod_tip": "8fc29454de466e975bad4dc0066a21da310b1ff5",
        "pack": pack,
        "probe_agent_id": agent_id,
        "probe_agent_name": probe_name,
        "pre_cleanup": {
            "uninstall_http": pre_uninstall.status_code,
            "assignments_cleared": cleared,
        },
        "http_install": {"status": install.status_code, "body": body},
        "http_uninstall": {
            "status": uninstall.status_code,
            "body": uninstall.json() if uninstall.content else {},
        },
        "install_row": install_row[0] if install_row else None,
        "audits": audits,
        "verdict": "PASS" if ok else "FAIL",
    }
    OUT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    # Merge into combined artifact if present
    if COMBINED.is_file():
        combined = json.loads(COMBINED.read_text(encoding="utf-8"))
        combined.setdefault("traces", {})["P5_intelligence_pack_install"] = {
            "ticket": "STA-310",
            "path": "POST /api/marketplace/assets/{ref}/install asset_type=intelligence_pack",
            "install_http": install.status_code,
            "install_response": body if isinstance(body, dict) else {"raw": body},
            "audits": audits[:5],
            "install_row": install_row[0] if install_row else None,
            "verdict": report["verdict"],
            "pass_checks": {
                "http_ok": install.status_code in {200, 201},
                "intelligence_pack_entity": bool(
                    (isinstance(body, dict) and body.get("assetType") == "intelligence_pack")
                    or (install_row and install_row[0].get("installed_entity_type") == "intelligence_pack")
                ),
                "audit_evidence": bool(audits),
            },
            "dedicated_artifact": str(OUT.as_posix()),
        }
        verdicts = {
            "P4": combined.get("traces", {}).get("P4_uninstall_teardown", {}).get("verdict"),
            "P5": report["verdict"],
            "P6": combined.get("traces", {}).get("P6_department_member_audit", {}).get("verdict"),
        }
        combined["verdicts"] = verdicts
        combined["overall"] = (
            "PASS" if all(v == "PASS" for v in verdicts.values()) else "FAIL"
        )
        combined["option_a_applied"] = True
        combined["finished_at"] = utcnow()
        COMBINED.write_text(json.dumps(combined, indent=2, default=str) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "http": install.status_code,
                "overall_combined": (
                    json.loads(COMBINED.read_text(encoding="utf-8")).get("overall")
                    if COMBINED.is_file()
                    else None
                ),
                "out": str(OUT),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
