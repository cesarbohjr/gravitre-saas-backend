#!/usr/bin/env python3
"""Prove side-rail intel APIs fire only after chat is interactive (Phase 1)."""
from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "delivery" / "phase1-mount-defer-proof.json"


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
    auth_path = ROOT / "docs" / "delivery" / "_phase4-auth-session.json"
    if auth_path.is_file():
        blob = json.loads(auth_path.read_text(encoding="utf-8"))
        if blob.get("email") and blob.get("password"):
            merged.setdefault("CLICK_AUDIT_EMAIL", blob["email"])
            merged.setdefault("CLICK_AUDIT_PASSWORD", blob["password"])
    return merged


def main() -> int:
    env = load_env()
    email = env["CLICK_AUDIT_EMAIL"]
    password = env["CLICK_AUDIT_PASSWORD"]
    supabase = env["SUPABASE_URL"].rstrip("/")
    r = httpx.post(
        f"{supabase}/auth/v1/token?grant_type=password",
        headers={"apikey": env["SUPABASE_ANON_KEY"], "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=60,
    )
    r.raise_for_status()
    session = r.json()

    base = "https://gravitre.app"
    t0 = time.perf_counter()
    intel: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        ref = urlparse(env["SUPABASE_URL"]).hostname.split(".")[0]
        payload = base64.b64encode(json.dumps(session).encode("utf-8")).decode("ascii")
        context.add_cookies(
            [
                {
                    "name": f"sb-{ref}-auth-token",
                    "value": f"base64-{payload}",
                    "url": base + "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                }
            ]
        )
        page = context.new_page()

        def _on_request(req):
            if "/api/assistant/business-signals" in req.url or "/api/assistant/advisor-brief" in req.url:
                intel.append(
                    {
                        "t_ms": round((time.perf_counter() - t0) * 1000),
                        "url": req.url.split("?")[0],
                    }
                )

        page.on("request", _on_request)
        page.goto(f"{base}/ai", wait_until="domcontentloaded", timeout=90_000)
        if "/login" in page.url:
            page.goto(f"{base}/login?intent=login", wait_until="domcontentloaded", timeout=90_000)
            page.get_by_placeholder("you@company.com").fill(email)
            page.get_by_placeholder("Enter your password").fill(password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_function("() => !location.pathname.startsWith('/login')", timeout=90_000)
        page.evaluate(
            """() => {
              localStorage.setItem('gravitre-welcome-dismissed', 'true');
              localStorage.removeItem('gravitre-nav-expanded');
            }"""
        )
        page.locator("aside nav").first.wait_for(state="visible", timeout=60_000)
        ai_nav = page.locator("aside nav a[href='/ai'], aside nav a[href^='/ai?']").first
        if ai_nav.count() > 0:
            ai_nav.click()
        else:
            page.goto(f"{base}/ai", wait_until="domcontentloaded", timeout=90_000)
        page.wait_for_selector("textarea", state="visible", timeout=60_000)
        interactive_at = round((time.perf_counter() - t0) * 1000)
        page.wait_for_timeout(4000)
        waited_until = round((time.perf_counter() - t0) * 1000)
        browser.close()

    before = [row for row in intel if row["t_ms"] < interactive_at]
    after = [row for row in intel if row["t_ms"] >= interactive_at]
    out = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "api_health_git_sha": httpx.get("https://api.gravitre.app/health", timeout=30).json().get(
            "git_sha"
        ),
        "chat_input_interactive_ms": interactive_at,
        "waited_until_ms": waited_until,
        "mount_intel_before_interactive": before,
        "mount_intel_after_interactive": after,
        "all_mount_intel_api_requests": intel,
        "verdict": "PASS" if (not before and after) else ("PARTIAL" if not before else "FAIL"),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
