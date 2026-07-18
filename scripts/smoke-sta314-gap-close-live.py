"""STA-314 gap-close prod smoke: real org signals + GET + UI contract evidence."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local"]:
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
        for k, v in loaded.items():
            if v:
                os.environ.setdefault(k, v)

sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings
from app.services.recommendation_heuristics_service import (
    assert_no_execute_surface,
    build_heuristic_recommendations,
    filter_dismissed_recommendations,
    load_dismissed_card_ids,
    load_heuristic_signals,
)
from app.workflows.repository import get_supabase_client

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"
BASE = os.environ.get("STA314_BASE_URL", "https://api.gravitre.app").rstrip("/")
OUT = ROOT / "docs" / "delivery" / "sta314-gap-close-live.json"
UI_COMPONENT = (
    ROOT
    / "apps"
    / "web"
    / "components"
    / "intelligence"
    / "heuristic-suggestion-cards.tsx"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint_token() -> str:
    client = get_supabase_client(get_settings())
    email = client.auth.admin.get_user_by_id(ACTOR).user.email
    url = os.environ["SUPABASE_URL"].rstrip("/")
    return jwt.encode(
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


def ui_evidence() -> dict:
    source = UI_COMPONENT.read_text(encoding="utf-8")
    return {
        "path": str(UI_COMPONENT.relative_to(ROOT)).replace("\\", "/"),
        "hasOpenNav": "Open" in source and "href={card.href}" in source,
        "hasDismiss": 'data-testid="heuristic-card-dismiss"' in source,
        "bansExecuteHandlers": not any(
            token in source
            for token in ("onExecute", "handleExecute", "executePlan", "invoke_tool")
        ),
        "bansExecuteLabels": not any(
            label in source for label in (">Execute<", ">Apply<", ">Install<", ">Run<", ">Schedule<")
        ),
        "advisoryCopy": "Advisory only" in source,
    }


def main() -> int:
    settings = get_settings()
    client = get_supabase_client(settings)

    signals = load_heuristic_signals(client, ORG)
    local_payload = build_heuristic_recommendations(
        connected_connectors=signals["connected_connectors"],
        usage_by_connector=signals["usage_by_connector"],
        installed_packs=signals["installed_packs"],
        lookback_days=int(signals.get("lookback_days") or 30),
    )
    dismissed = load_dismissed_card_ids(client, ORG, ACTOR)
    local_payload = filter_dismissed_recommendations(local_payload, dismissed)
    assert_no_execute_surface(local_payload)

    tok = mint_token()
    hdr = {
        "Authorization": f"Bearer {tok}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }
    get_res = httpx.get(
        f"{BASE}/api/intelligence/recommendations/heuristics",
        headers=hdr,
        timeout=60,
    )
    get_body: dict = {}
    try:
        get_body = get_res.json()
    except Exception:
        get_body = {"raw": get_res.text[:2000]}

    http_ok = get_res.status_code == 200
    http_advisory = bool(isinstance(get_body, dict) and get_body.get("advisoryOnly") is True)
    http_no_actions = bool(isinstance(get_body, dict) and get_body.get("actionsTaken") == [])
    if http_ok and isinstance(get_body, dict):
        try:
            assert_no_execute_surface(get_body)
            http_no_execute = True
        except AssertionError as exc:
            http_no_execute = False
            get_body = {**get_body, "_executeSurfaceError": str(exc)}
    else:
        http_no_execute = False

    dismiss_probe_id = "sta314-smoke-probe-unused-slack"
    dismiss_res = httpx.post(
        f"{BASE}/api/intelligence/recommendations/heuristics/{dismiss_probe_id}/dismiss",
        headers=hdr,
        json={},
        timeout=60,
    )
    dismiss_body: dict = {}
    try:
        dismiss_body = dismiss_res.json()
    except Exception:
        dismiss_body = {"raw": dismiss_res.text[:1000]}

    ui = ui_evidence()
    evidence = {
        "ticket": "STA-314",
        "kind": "gap-close-live",
        "ran_at": utcnow(),
        "org_id": ORG,
        "actor_id": ACTOR,
        "base_url": BASE,
        "signals": {
            "connectorCount": len(signals["connected_connectors"]),
            "connectors": [
                {
                    "vendor": c.get("vendor"),
                    "label": c.get("label"),
                    "status": c.get("status"),
                    "executable": c.get("executable"),
                }
                for c in signals["connected_connectors"][:20]
            ],
            "usageByConnector": signals["usage_by_connector"],
            "installedPackCount": len(signals["installed_packs"]),
            "installedPacksSample": sorted(signals["installed_packs"])[:30],
            "dismissedCount": len(dismissed),
        },
        "local_builder": {
            "advisoryOnly": local_payload.get("advisoryOnly"),
            "actionsTaken": local_payload.get("actionsTaken"),
            "count": local_payload.get("count"),
            "kinds": [c.get("kind") for c in local_payload.get("recommendations") or []],
            "noExecuteSurface": True,
        },
        "http_get": {
            "status": get_res.status_code,
            "advisoryOnly": http_advisory,
            "actionsTakenEmpty": http_no_actions,
            "noExecuteSurface": http_no_execute,
            "count": get_body.get("count") if isinstance(get_body, dict) else None,
            "kinds": (
                [c.get("kind") for c in (get_body.get("recommendations") or [])]
                if isinstance(get_body, dict)
                else []
            ),
            "body": get_body,
            "note": (
                "HTTP reflects currently deployed Railway revision; "
                "local_builder uses gap-close signal wiring against prod DB."
            ),
        },
        "http_dismiss_probe": {
            "status": dismiss_res.status_code,
            "body": dismiss_body,
            "expectedAfterDeploy": 200,
        },
        "ui_evidence": ui,
        "pass": {
            "localSignalsLoaded": True,
            "localNoExecute": True,
            "httpGet200": http_ok,
            "httpAdvisoryOnly": http_advisory and http_no_actions and http_no_execute,
            "uiNavAndDismissOnly": all(
                [
                    ui["hasOpenNav"],
                    ui["hasDismiss"],
                    ui["bansExecuteHandlers"],
                    ui["bansExecuteLabels"],
                ]
            ),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "pass": evidence["pass"]}, indent=2))
    ok = (
        evidence["pass"]["localNoExecute"]
        and evidence["pass"]["httpGet200"]
        and evidence["pass"]["httpAdvisoryOnly"]
        and evidence["pass"]["uiNavAndDismissOnly"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
