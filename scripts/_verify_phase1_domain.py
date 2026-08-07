#!/usr/bin/env python3
"""Live verify Phase 1 domain / OG / Support Live Chat."""
from __future__ import annotations

import json
import re
import urllib.request

HOME = "https://gravitre.app/"
SUPPORT = "https://gravitre.app/support"
HEALTH = "https://api.gravitre.app/health"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "gravitre-phase1-verify/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main() -> int:
    health = json.loads(fetch(HEALTH))
    home = fetch(HOME)
    support = fetch(SUPPORT)

    def meta(html: str, prop: str) -> str | None:
        m = re.search(
            rf'(?:property|name|rel)=["\']{re.escape(prop)}["\'][^>]*?(?:content|href)=["\']([^"\']+)',
            html,
            re.I,
        )
        if m:
            return m.group(1)
        m = re.search(
            rf'(?:content|href)=["\']([^"\']+)["\'][^>]*?(?:property|name|rel)=["\']{re.escape(prop)}',
            html,
            re.I,
        )
        return m.group(1) if m else None

    report = {
        "api_git_sha": health.get("git_sha"),
        "canonical": meta(home, "canonical"),
        "og:url": meta(home, "og:url"),
        "og:image": meta(home, "og:image"),
        "home_gravitre_com_count": home.count("gravitre.com"),
        "home_gravitre_app_count": home.count("gravitre.app"),
        "support_has_contact": "/contact" in support,
        "support_has_dead_chat": "gravitre.com/chat" in support,
        "support_live_chat_href": None,
    }
    # Live Chat card: href may be hundreds of chars before the heading (icons/SVG).
    m = re.search(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[\s\S]{0,1200}?Live Chat',
        support,
        re.I,
    )
    if m:
        report["support_live_chat_href"] = m.group(1)
    report["support_contact_href_present"] = 'href="/contact"' in support or "href='/contact'" in support

    ok = (
        report["canonical"]
        and "gravitre.app" in (report["canonical"] or "")
        and "gravitre.com" not in (report["canonical"] or "")
        and report["support_has_contact"]
        and not report["support_has_dead_chat"]
        and (
            (report["support_live_chat_href"] or "").startswith("/contact")
            or report["support_contact_href_present"]
        )
    )
    report["pass"] = bool(ok)
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
