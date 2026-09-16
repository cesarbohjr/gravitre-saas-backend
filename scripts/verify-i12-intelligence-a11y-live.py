#!/usr/bin/env python3
"""I12 — live Intelligence a11y + List vs canvas screenshots on gravitre.app.

Reuses G8 UI login (billing fixture password, else JWT inject).
Writes docs/delivery/i12-intelligence-a11y-live.json and PNG artifacts.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

_ui_spec = importlib.util.spec_from_file_location(
    "verify_g8_intelligence_hub_ui_live",
    ROOT / "scripts" / "verify-g8-intelligence-hub-ui-live.py",
)
assert _ui_spec and _ui_spec.loader
_ui = importlib.util.module_from_spec(_ui_spec)
_ui_spec.loader.exec_module(_ui)

OUT = ROOT / "docs" / "delivery" / "i12-intelligence-a11y-live.json"
ART = ROOT / "docs" / "delivery" / "_ci-artifacts"
WEB_BASE = os.environ.get("INTELLIGENCE_UI_BASE", "https://gravitre.app").rstrip("/")
AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"

SERIOUS_IMPACTS = {"critical", "serious"}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_axe(page: Any) -> dict[str, Any]:
    page.add_script_tag(url=AXE_CDN)
    page.wait_for_function("() => typeof window.axe === 'object'", timeout=20_000)
    return page.evaluate(
        """async () => {
          const results = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] },
          });
          const interesting = (results.violations || []).map((v) => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            helpUrl: v.helpUrl,
            nodes: (v.nodes || []).slice(0, 8).map((n) => ({
              html: (n.html || '').slice(0, 240),
              target: n.target,
              failureSummary: (n.failureSummary || '').slice(0, 400),
            })),
          }));
          return {
            url: location.href,
            violationCount: (results.violations || []).length,
            seriousOrCritical: interesting.filter((v) => v.impact === 'critical' || v.impact === 'serious').length,
            violations: interesting,
            passesSample: (results.passes || []).slice(0, 12).map((p) => p.id),
          };
        }"""
    )


def login(page: Any) -> tuple[str, str]:
    env = _ui.load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    trust = _ui.resolve_trust_org_actor(env, sb)
    if not trust:
        raise RuntimeError("OPERATOR_USER_ID not resolvable")
    org_id, user_id, email = trust
    login_mode = "jwt_inject"
    login_email = email
    login_password = ""
    try:
        sys.path.insert(0, str(ROOT / "e2e"))
        from helpers.auth import loadBillingFixtures  # type: ignore

        fixture = loadBillingFixtures().activeTrial
        login_email = fixture.email
        login_password = fixture.password
        org_id = fixture.orgId
        login_mode = "billing_fixture_password"
    except Exception:  # noqa: BLE001
        pass
    if login_password:
        _ui.login_with_password(page, login_email, login_password, org_id)
    else:
        _ui.inject_auth_session(page, env, user_id, email, org_id)
    return org_id, login_mode


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        report = {
            "probe": "i12_intelligence_a11y_live",
            "started_at": utcnow(),
            "verdict": "NOT RUN",
            "reason": f"playwright not installed: {exc}",
        }
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    ART.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "probe": "i12_intelligence_a11y_live",
        "started_at": utcnow(),
        "web_base": WEB_BASE,
        "cases": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            org_id, login_mode = login(page)
            report["org_id"] = org_id
            report["login_mode"] = login_mode

            with page.expect_response(
                lambda r: "/api/intelligence/page-context" in r.url and r.status == 200,
                timeout=90_000,
            ):
                page.goto(f"{WEB_BASE}/intelligence", timeout=90_000)
            page.get_by_test_id("intelligence-map-canvas").wait_for(state="visible", timeout=60_000)
            canvas_png = ART / "i12-overview-canvas.png"
            page.screenshot(path=str(canvas_png), full_page=True)
            report["cases"].append(
                {
                    "id": "overview-canvas-screenshot",
                    "passed": True,
                    "verdict": "PASS",
                    "screenshot": str(canvas_png.relative_to(ROOT)),
                    "url": page.url,
                }
            )

            overview_axe = run_axe(page)
            serious = int(overview_axe.get("seriousOrCritical") or 0)
            report["cases"].append(
                {
                    "id": "overview-axe",
                    "passed": serious == 0,
                    "verdict": "PASS" if serious == 0 else "FAIL",
                    **overview_axe,
                }
            )

            list_btn = page.get_by_role("button", name="List")
            if list_btn.count() == 0:
                list_btn = page.get_by_test_id("intelligence-graph-list-toggle")
            if list_btn.count() == 0:
                report["cases"].append(
                    {
                        "id": "overview-list-screenshot",
                        "passed": True,
                        "verdict": "NOT RUN",
                        "reason": "List control not found on Overview",
                    }
                )
            else:
                list_btn.first.click()
                page.get_by_role("list").first.wait_for(state="visible", timeout=15_000)
                list_png = ART / "i12-overview-list.png"
                page.screenshot(path=str(list_png), full_page=True)
                report["cases"].append(
                    {
                        "id": "overview-list-screenshot",
                        "passed": True,
                        "verdict": "PASS",
                        "screenshot": str(list_png.relative_to(ROOT)),
                        "url": page.url,
                    }
                )

            with page.expect_response(
                lambda r: "/api/intelligence/page-context" in r.url and r.status == 200,
                timeout=90_000,
            ):
                page.goto(f"{WEB_BASE}/intelligence/reports", timeout=90_000)
            time.sleep(2)
            reports_png = ART / "i12-reports.png"
            page.screenshot(path=str(reports_png), full_page=True)
            reports_axe = run_axe(page)
            reports_serious = int(reports_axe.get("seriousOrCritical") or 0)
            report["cases"].append(
                {
                    "id": "reports-screenshot",
                    "passed": True,
                    "verdict": "PASS",
                    "screenshot": str(reports_png.relative_to(ROOT)),
                    "url": page.url,
                }
            )
            report["cases"].append(
                {
                    "id": "reports-axe",
                    "passed": reports_serious == 0,
                    "verdict": "PASS" if reports_serious == 0 else "FAIL",
                    **reports_axe,
                }
            )
        except Exception as exc:  # noqa: BLE001
            fail_png = ART / "i12-a11y-failure.png"
            try:
                page.screenshot(path=str(fail_png), full_page=True)
                report["debug_screenshot"] = str(fail_png.relative_to(ROOT))
            except Exception:  # noqa: BLE001
                pass
            report["cases"].append(
                {
                    "id": "i12-a11y-battery",
                    "passed": False,
                    "verdict": "FAIL",
                    "error": f"{exc.__class__.__name__}: {exc}",
                    "page_url": page.url,
                }
            )
        finally:
            browser.close()

    runnable = [c for c in report["cases"] if c.get("verdict") != "NOT RUN"]
    report["finished_at"] = utcnow()
    if not runnable:
        report["verdict"] = "NOT RUN"
    else:
        report["verdict"] = "PASS" if all(c.get("passed") for c in runnable) else "FAIL"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report.get("verdict"), "cases": report.get("cases")}, indent=2)[:8000])
    if report.get("verdict") == "NOT RUN":
        return 2
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
