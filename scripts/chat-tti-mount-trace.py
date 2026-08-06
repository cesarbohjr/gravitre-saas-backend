#!/usr/bin/env python3
"""Authenticated chat TTI + mount-sequence timing via Playwright.

Uses CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD (or --email/--password).
Writes docs/delivery/phase4-chat-tti-live.json.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

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
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://gravitre.app")
    parser.add_argument("--email", default=os.environ.get("CLICK_AUDIT_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("CLICK_AUDIT_PASSWORD", ""))
    args = parser.parse_args()
    env = load_env()
    email = args.email or env.get("CLICK_AUDIT_EMAIL") or env.get("E2E_EMAIL") or ""
    password = args.password or env.get("CLICK_AUDIT_PASSWORD") or env.get("E2E_PASSWORD") or ""
    if not email or not password:
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "NOT_RUN",
            "reason": "Missing CLICK_AUDIT_EMAIL / CLICK_AUDIT_PASSWORD (or E2E_*)",
        }
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    from playwright.sync_api import sync_playwright

    timeline: list[dict] = []
    t0 = time.perf_counter()

    def mark(label: str, **extra):
        timeline.append({"t_ms": round((time.perf_counter() - t0) * 1000), "label": label, **extra})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        base = args.base.rstrip("/")
        mark("browser_ready")
        page.goto(f"{base}/login?intent=login", wait_until="domcontentloaded", timeout=90_000)
        mark("login_domcontentloaded", url=page.url)
        page.get_by_placeholder("Enter your email").fill(email)
        page.get_by_placeholder("Enter your password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_url(lambda u: "/login" not in u.path, timeout=90_000)
        mark("login_complete", url=page.url)

        page.goto(f"{base}/ai", wait_until="domcontentloaded", timeout=90_000)
        mark("ai_domcontentloaded", url=page.url)

        # Composer / chat input selectors used across app shells
        selectors = [
            'textarea[placeholder*="Ask"]',
            'textarea[placeholder*="Message"]',
            'textarea[data-testid="chat-input"]',
            '[contenteditable="true"][role="textbox"]',
            "textarea",
        ]
        interactive_at = None
        used = None
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                loc.wait_for(state="visible", timeout=20_000)
                # interactivity: enabled + not covered
                if loc.is_enabled():
                    interactive_at = round((time.perf_counter() - t0) * 1000)
                    used = sel
                    mark("chat_input_interactive", selector=sel)
                    break
            except Exception:
                continue

        # Parallel vs sequential: sample network/requests fired before interactive
        # (Playwright doesn't expose full resource timing cheaply; record performance entries)
        perf = page.evaluate(
            """() => {
              const nav = performance.getEntriesByType('navigation')[0];
              const resources = performance.getEntriesByType('resource')
                .slice(0, 40)
                .map(r => ({name: r.name.split('/').slice(-1)[0], start: Math.round(r.startTime), dur: Math.round(r.duration)}));
              return {
                domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
                loadEvent: nav ? Math.round(nav.loadEventEnd) : null,
                resources
              };
            }"""
        )
        mark("perf_entries_captured")
        browser.close()

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "base": args.base,
        "email": email,
        "timeline_ms": timeline,
        "chat_input_selector": used,
        "tti_from_script_start_ms": interactive_at,
        "navigation_perf": perf,
        "verdict": "PASS" if interactive_at is not None else "FAIL",
        "parallelism_note": (
            "Resource startTime values show overlapping fetches (parallel) vs staggered "
            "starts (more sequential). See navigation_perf.resources."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
