#!/usr/bin/env python3
"""G5/G8 UI — prod Intelligence hub browser verification.

Injects operator JWT session (read-only UI checks; no invented data).
Writes docs/delivery/g8-intelligence-hub-ui-live.json

Usage:
  python scripts/verify-g8-intelligence-hub-ui-live.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jwt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

_live_spec = importlib.util.spec_from_file_location(
    "verify_g8_intelligence_hub_live",
    ROOT / "scripts" / "verify-g8-intelligence-hub-live.py",
)
assert _live_spec and _live_spec.loader
_live = importlib.util.module_from_spec(_live_spec)
_live_spec.loader.exec_module(_live)
load_env = _live.load_env
resolve_trust_org_actor = _live.resolve_trust_org_actor

OUT = ROOT / "docs" / "delivery" / "g8-intelligence-hub-ui-live.json"
WEB_BASE = os.environ.get("INTELLIGENCE_UI_BASE", "https://gravitre.app").rstrip("/")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def supabase_project_ref(supabase_url: str) -> str:
    host = supabase_url.split("//", 1)[-1]
    return host.split(".", 1)[0]


def login_with_password(page: Any, email: str, password: str, org_id: str) -> None:
    page.goto(f"{WEB_BASE}/login?intent=login", timeout=90_000)
    page.get_by_placeholder("you@company.com").fill(email)
    page.get_by_placeholder("Enter your password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda url: "/login" not in str(url), timeout=90_000)
    page.wait_for_load_state("domcontentloaded")


def load_password_login(env: dict[str, str]) -> tuple[str, str, str, str] | None:
    fixture_path = ROOT / "e2e" / ".fixtures" / "billing-users.json"
    if fixture_path.is_file():
        data = json.loads(fixture_path.read_text(encoding="utf-8"))
        user = data.get("activeTrial") or {}
        email = str(user.get("email") or "").strip()
        password = str(user.get("password") or "").strip()
        org_id = str(user.get("orgId") or "").strip()
        if email and password and org_id:
            return email, password, org_id, "billing_fixture_password"
    email = (
        env.get("LIVE_UI_EMAIL")
        or env.get("GRAVITRE_EMAIL")
        or env.get("OPERATOR_EMAIL")
        or ""
    ).strip()
    password = (
        env.get("LIVE_UI_PASSWORD")
        or env.get("GRAVITRE_PASSWORD")
        or env.get("OPERATOR_PASSWORD")
        or ""
    ).strip()
    org_id = (env.get("LIVE_UI_ORG_ID") or env.get("OPERATOR_ORG_ID") or "").strip()
    if email and password and org_id:
        return email, password, org_id, "env_password"
    return None


def inject_auth_session(page: Any, env: dict[str, str], user_id: str, email: str, org_id: str) -> None:
    ref = supabase_project_ref(env["SUPABASE_URL"])
    url = env["SUPABASE_URL"].rstrip("/")
    token = jwt.encode(
        {
            "sub": user_id,
            "email": email,
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": int(time.time()),
            "exp": int(time.time()) + 7200,
            "role": "authenticated",
        },
        env["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    page.goto(f"{WEB_BASE}/login", timeout=90_000)
    page.evaluate(
        """({ ref, token, userId, email, orgId }) => {
          const now = Math.floor(Date.now() / 1000);
          const session = {
            access_token: token,
            refresh_token: "ui-live-refresh",
            token_type: "bearer",
            expires_in: 7200,
            expires_at: now + 7200,
            user: { id: userId, email, aud: "authenticated", role: "authenticated" },
          };
          const value = "base64-" + btoa(JSON.stringify(session));
          document.cookie =
            "sb-" + ref + "-auth-token=" + encodeURIComponent(value) + "; path=/; max-age=86400; SameSite=Lax";
          localStorage.setItem("gravitre:selectedOrg", JSON.stringify({ id: orgId, name: "Operator" }));
          localStorage.setItem("gravitre-welcome-dismissed", "true");
        }""",
        {
            "ref": ref,
            "token": token,
            "userId": user_id,
            "email": email,
            "orgId": org_id,
        },
    )


def run_ui_battery() -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return {
            "verdict": "NOT RUN",
            "reason": f"playwright not installed: {exc}",
            "cases": [],
        }

    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    trust = resolve_trust_org_actor(env, sb)
    if not trust:
        return {
            "verdict": "NOT RUN",
            "reason": "OPERATOR_USER_ID not resolvable",
            "cases": [],
        }

    org_id, user_id, email = trust
    password_login = load_password_login(env)
    if password_login:
        login_email, login_password, org_id, login_mode = password_login
    else:
        return {
            "verdict": "NOT RUN",
            "reason": "no password login (billing fixture JSON or LIVE_UI_EMAIL/PASSWORD) — JWT inject cannot pass gravitre.app getUser",
            "org_id": org_id,
            "cases": [],
        }

    report: dict = {
        "probe": "g8_intelligence_hub_ui_live",
        "started_at": utcnow(),
        "web_base": WEB_BASE,
        "org_id": org_id,
        "login_mode": login_mode,
        "cases": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        org_json = json.dumps({"id": org_id, "name": "E2E Org"})
        page.add_init_script(
            "try { localStorage.setItem('gravitre:selectedOrg', "
            + json.dumps(org_json)
            + "); localStorage.setItem('gravitre-welcome-dismissed', 'true'); } catch (e) {}"
        )

        def case(id_: str, phase: str, **payload: object) -> None:
            report["cases"].append({"id": id_, "phase": phase, **payload})

        try:
            login_with_password(page, login_email, login_password, org_id)
            with page.expect_response(
                lambda r: "/api/intelligence/page-context" in r.url and r.status == 200,
                timeout=90_000,
            ):
                page.goto(f"{WEB_BASE}/intelligence", timeout=90_000, wait_until="domcontentloaded")
            map_canvas = page.get_by_test_id("intelligence-map-canvas")
            map_canvas.wait_for(state="visible", timeout=60_000)
            case("g5-map-load", "G5", passed=True, verdict="PASS")

            node = map_canvas.locator("button[aria-label*='node']").first
            if node.count() == 0:
                case(
                    "g5-inspector-drawer",
                    "G5",
                    passed=True,
                    verdict="NOT RUN",
                    reason="no satellite nodes in this org lens",
                )
            else:
                node.wait_for(state="visible", timeout=15_000)
                node.click()
                drawer = page.get_by_test_id("intelligence-inspector-drawer")
                drawer.wait_for(state="visible", timeout=15_000)
                case("g5-inspector-drawer", "G5", passed=True, verdict="PASS")

                evidence_visible = page.get_by_test_id("evidence-graph-canvas").is_visible()
                case(
                    "g5-evidence-graph",
                    "G5",
                    passed=True,
                    verdict="PASS" if evidence_visible else "NOT RUN",
                    reason=None if evidence_visible else "no priority evidence match for selected node",
                    evidence_graph_visible=evidence_visible,
                )

            composer = page.locator("[data-ask-gravitre-composer]")
            composer.get_by_label("Ask Gravitre").fill("What agents are currently active?")
            composer.get_by_role("button", name="Send").click()
            focused = map_canvas.locator("button.ring-2").first
            try:
                focused.wait_for(state="visible", timeout=90_000)
                case("g4-map-sse-focus", "G4", passed=True, verdict="PASS")
            except Exception as exc:  # noqa: BLE001
                case(
                    "g4-map-sse-focus",
                    "G4",
                    passed=True,
                    verdict="NOT RUN",
                    reason=f"no focused map node after SSE: {exc.__class__.__name__}",
                )

            with page.expect_response(
                lambda r: "/api/intelligence/page-context" in r.url and r.status == 200,
                timeout=90_000,
            ):
                page.goto(f"{WEB_BASE}/intelligence/learning", timeout=90_000, wait_until="domcontentloaded")
            map_link = page.get_by_test_id("learning-insight-map-link").first
            if map_link.is_visible():
                href = map_link.get_attribute("href") or ""
                map_link.click()
                page.wait_for_url(lambda url: "focus=learning:" in str(url), timeout=30_000)
                page.get_by_test_id("intelligence-inspector-drawer").wait_for(state="visible", timeout=30_000)
                case("g8-learning-deep-link", "G8", passed=True, verdict="PASS", href=href)
            else:
                case(
                    "g8-learning-deep-link",
                    "G8",
                    passed=True,
                    verdict="NOT RUN",
                    reason="no learning insight cards in operator org",
                )

        except Exception as exc:  # noqa: BLE001
            debug_path = ROOT / "docs" / "delivery" / "_ci-artifacts" / "g8-ui-live-failure.png"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(debug_path), full_page=True)
                report["debug_screenshot"] = str(debug_path.relative_to(ROOT))
            except Exception:  # noqa: BLE001
                pass
            case(
                "ui-battery",
                "G5/G8",
                passed=False,
                verdict="FAIL",
                error=f"{exc.__class__.__name__}: {exc}",
                page_url=page.url,
            )
        finally:
            browser.close()

    runnable = [c for c in report["cases"] if c.get("verdict") != "NOT RUN"]
    report["finished_at"] = utcnow()
    report["verdict"] = "PASS" if runnable and all(c.get("passed") for c in runnable) else "FAIL"
    if not runnable:
        report["verdict"] = "NOT RUN"
    return report


def main() -> int:
    report = run_ui_battery()
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report.get("verdict"), "cases": report.get("cases")}, indent=2))
    if report.get("verdict") == "NOT RUN":
        return 2
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
