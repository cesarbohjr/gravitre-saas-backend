#!/usr/bin/env python3
"""Extract performance scores from uploaded LHCI HTML reports."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

REPORTS = {
    "home": "https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785983627565-97049.report.html",
    "pricing": "https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785983628032-81146.report.html",
}
OUT = Path("docs/delivery/phase2-lighthouse-scores-live.json")


def extract(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "gravitre-lh-extract/1.0"})
    html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", errors="ignore")
    m = re.search(
        r"window\.__LIGHTHOUSE_JSON__\s*=\s*(\{.*?\})\s*;?\s*</script>",
        html,
        re.S,
    )
    if not m:
        # Fallback: score near categories.performance
        sm = re.search(r'"performance"\s*:\s*\{\s*"title"\s*:\s*"Performance"\s*,\s*"score"\s*:\s*([0-9.]+)', html)
        return {"url": url, "performance": float(sm.group(1)) if sm else None, "raw_match": bool(sm)}
    data = json.loads(m.group(1))
    audits = data.get("audits") or {}
    return {
        "requestedUrl": data.get("requestedUrl"),
        "performance": (data.get("categories") or {}).get("performance", {}).get("score"),
        "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue"),
        "si_ms": audits.get("speed-index", {}).get("numericValue"),
        "tbt_ms": audits.get("total-blocking-time", {}).get("numericValue"),
        "fcp_ms": audits.get("first-contentful-paint", {}).get("numericValue"),
        "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
        "report_url": url,
    }


def main() -> int:
    pages = {name: extract(url) for name, url in REPORTS.items()}
    home_score = pages.get("home", {}).get("performance")
    report = {
        "ci_run": "https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31065773698",
        "tip_sha": "4cf35bcb8d3acc052759e91a7fb1de4a10dcbb78",
        "pages": pages,
        "home_meets_0_75": isinstance(home_score, (int, float)) and home_score >= 0.75,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["home_meets_0_75"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
