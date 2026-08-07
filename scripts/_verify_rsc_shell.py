#!/usr/bin/env python3
"""Live View-Source / RSC flight check for / and /pricing.

Answers whether the server shell delivers meaningful SSR content vs client-island dominance.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone

URLS = ("https://gravitre.app/", "https://gravitre.app/pricing")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "gravitre-rsc-check/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def analyze(url: str, html: str) -> dict:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Meaningful marketing copy markers
    markers = {
        "has_h1": bool(re.search(r"<h1[\s>]", html, re.I)),
        "has_cta_get_started": "get-started" in html.lower() or "Get Started" in html,
        "has_pricing_copy": "pricing" in html.lower() or "$" in html,
        "rsc_flight_payload": "self.__next_f.push" in html or "$RC=" in html or "S:" in html[:2000],
        "client_island_hints": {
            "HeroParallax": "HeroParallax" in html,
            "framer-motion": "framer-motion" in html or "animate" in html[:5000],
            "use client chunks": bool(re.search(r"static/chunks/.*\.js", html)),
        },
    }
    # Count visible words in SSR HTML (approx)
    words = [w for w in text.split(" ") if len(w) > 2]
    sample = " ".join(words[:80])
    return {
        "url": url,
        "html_bytes": len(html.encode("utf-8")),
        "ssr_visible_words": len(words),
        "ssr_text_sample": sample,
        "markers": markers,
        "verdict": (
            "SERVER_SHELL_MEANINGFUL"
            if markers["has_h1"] and len(words) >= 40
            else "CLIENT_DOMINATED_OR_THIN_SSR"
        ),
    }


def main() -> int:
    reports = [analyze(u, fetch(u)) for u in URLS]
    out = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "pages": reports,
        "summary": {
            "all_meaningful_ssr": all(p["verdict"] == "SERVER_SHELL_MEANINGFUL" for p in reports),
            "note": (
                "RSC shells can still hydrate client islands; this checks whether the initial "
                "HTML already contains real marketing copy (h1 + substantial text), not empty shells."
            ),
        },
    }
    path = "docs/delivery/phase4-rsc-shell-live.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"wrote {path}")
    return 0 if out["summary"]["all_meaningful_ssr"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
