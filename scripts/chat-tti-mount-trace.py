#!/usr/bin/env python3
"""Authenticated chat TTI + mount-sequence timing via Playwright.

Prefers password-grant → session cookie injection (more reliable than UI login).
Falls back to form login. Credentials: CLICK_AUDIT_* or docs/delivery/_phase4-auth-session.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "delivery" / "phase4-chat-tti-live.json"


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (
        ROOT / "backend" / ".env.operator.local",
        ROOT / "backend" / ".env",
        ROOT / ".env",
    ):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    auth_path = ROOT / "docs" / "delivery" / "_phase4-auth-session.json"
    if auth_path.is_file():
        try:
            blob = json.loads(auth_path.read_text(encoding="utf-8"))
            if blob.get("email") and blob.get("password"):
                merged.setdefault("CLICK_AUDIT_EMAIL", blob["email"])
                merged.setdefault("CLICK_AUDIT_PASSWORD", blob["password"])
        except json.JSONDecodeError:
            pass
    return merged


def password_grant(env: dict[str, str], email: str, password: str) -> dict:
    url = env["SUPABASE_URL"].rstrip("/")
    anon = env["SUPABASE_ANON_KEY"]
    r = httpx.post(
        f"{url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def seed_session_cookie(context, origin: str, supabase_url: str, session: dict) -> None:
    ref = urlparse(supabase_url).hostname.split(".")[0]
    # @supabase/ssr cookie format used by the web app
    payload = base64.b64encode(json.dumps(session).encode("utf-8")).decode("ascii")
    value = f"base64-{payload}"
    context.add_cookies(
        [
            {
                "name": f"sb-{ref}-auth-token",
                "value": value,
                "url": origin + "/",
                "httpOnly": False,
                "secure": origin.startswith("https"),
                "sameSite": "Lax",
            }
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://gravitre.app")
    parser.add_argument("--email", default="")
    parser.add_argument("--password", default="")
    args = parser.parse_args()
    env = load_env()
    email = args.email or env.get("CLICK_AUDIT_EMAIL") or ""
    password = args.password or env.get("CLICK_AUDIT_PASSWORD") or ""
    if not email or not password:
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "NOT_RUN",
            "reason": "Missing CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD",
        }
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    from playwright.sync_api import sync_playwright

    timeline: list[dict] = []
    t0 = time.perf_counter()

    def mark(label: str, **extra):
        timeline.append({"t_ms": round((time.perf_counter() - t0) * 1000), "label": label, **extra})

    session = password_grant(env, email, password)
    mark("password_grant_ok")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        base = args.base.rstrip("/")
        seed_session_cookie(context, base, env["SUPABASE_URL"], session)
        mark("session_cookie_seeded")
        page = context.new_page()
        blocked_mount_apis: list[dict] = []

        def _on_request(req):
            url = req.url
            if "/api/assistant/business-signals" in url or "/api/assistant/advisor-brief" in url:
                blocked_mount_apis.append(
                    {
                        "t_ms": round((time.perf_counter() - t0) * 1000),
                        "url": url.split("?")[0],
                    }
                )

        page.on("request", _on_request)

        page.goto(f"{base}/ai", wait_until="domcontentloaded", timeout=90_000)
        mark("ai_domcontentloaded", url=page.url)

        if "/login" in page.url:
            # Cookie shape may differ — fall back to UI login
            mark("cookie_rejected_fallback_ui_login")
            page.goto(f"{base}/login?intent=login", wait_until="domcontentloaded", timeout=90_000)
            page.get_by_placeholder("you@company.com").fill(email)
            page.get_by_placeholder("Enter your password").fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_function("() => !location.pathname.startsWith('/login')", timeout=90_000)
            mark("login_complete", url=page.url)
        page.evaluate(
            """() => {
              localStorage.setItem('gravitre-welcome-dismissed', 'true');
              localStorage.removeItem('gravitre-nav-expanded');
            }"""
        )
        # Authenticated shell TTI: sidebar is the first durable interactive signal.
        page.locator("aside nav").first.wait_for(state="visible", timeout=60_000)
        home_interactive_at = round((time.perf_counter() - t0) * 1000)
        mark("home_sidebar_interactive", url=page.url)

        # Prefer in-app nav to /ai (keeps auth cookies / org context).
        ai_nav = page.locator("aside nav a[href='/ai'], aside nav a[href^='/ai?']").first
        if ai_nav.count() > 0:
            ai_nav.click()
        else:
            page.goto(f"{base}/ai", wait_until="domcontentloaded", timeout=90_000)
        mark("ai_navigation", url=page.url)

        interactive_at = None
        used = None
        try:
            page.wait_for_selector("textarea", state="visible", timeout=60_000)
            loc = page.locator("textarea").first
            if loc.is_enabled():
                interactive_at = round((time.perf_counter() - t0) * 1000)
                used = "textarea"
                mark("chat_input_interactive", selector=used, url=page.url)
        except Exception as exc:
            mark("composer_wait_failed", error=str(exc)[:200], url=page.url)

        perf = page.evaluate(
            """() => {
              const nav = performance.getEntriesByType('navigation')[0];
              const resources = performance.getEntriesByType('resource')
                .slice(0, 50)
                .map(r => ({
                  name: r.name.split('/').slice(-1)[0].slice(0, 80),
                  start: Math.round(r.startTime),
                  dur: Math.round(r.duration),
                }));
              const overlapping = [];
              for (let i = 1; i < resources.length; i++) {
                if (resources[i].start < resources[i-1].start + resources[i-1].dur) {
                  overlapping.push([resources[i-1].name, resources[i].name]);
                }
              }
              return {
                domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
                loadEvent: nav ? Math.round(nav.loadEventEnd) : null,
                resourceCount: resources.length,
                overlappingPairs: overlapping.slice(0, 12),
                resources
              };
            }"""
        )
        mark("perf_entries_captured", final_url=page.url)
        browser.close()

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base": args.base,
        "email": email,
        "auth_mode": "password_grant_cookie_then_ui_login",
        "timeline_ms": timeline,
        "home_sidebar_interactive_ms": next(
            (e["t_ms"] for e in timeline if e["label"] == "home_sidebar_interactive"),
            None,
        ),
        "chat_input_selector": used,
        "chat_tti_from_script_start_ms": interactive_at,
        "mount_intel_api_requests": blocked_mount_apis,
        "mount_intel_before_interactive": [
            row
            for row in blocked_mount_apis
            if interactive_at is not None and row["t_ms"] < interactive_at
        ],
        "navigation_perf": perf,
        "verdict": (
            "PASS"
            if interactive_at is not None
            else (
                "PARTIAL_HOME_SHELL"
                if any(e["label"] == "home_sidebar_interactive" for e in timeline)
                else "FAIL"
            )
        ),
        "parallelism_note": (
            "overlappingPairs lists resource fetches whose intervals overlap "
            "(parallel). Empty/small set with large start gaps ≈ sequential."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
