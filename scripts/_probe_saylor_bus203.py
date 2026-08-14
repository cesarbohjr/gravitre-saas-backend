"""Probe Saylor BUS203 structure + Census ToS (one-off license/provenance probe)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (license-verify; support@gravitre.ai)"}
OUT = Path("docs/delivery/saylor-bus203-probe.json")


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def main() -> None:
    out: dict = {}
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        census = client.get("https://www.census.gov/data/developers/about/terms-of-service.html")
        cp = plain(census.text)
        census_snips = []
        for key in ("public domain", "copyright", "API Key", "You may", "prohibited", "attribution"):
            i = cp.lower().find(key.lower())
            if i >= 0:
                census_snips.append(cp[max(0, i - 40) : i + 200])
        out["census_tos"] = {"http": census.status_code, "snippets": census_snips}

        bus203 = client.get("https://learn.saylor.org/course/view.php?id=72")
        bp = plain(bus203.text)
        saylor_snips = []
        for key in ("Creative Commons", "Third-party", "Saylor University", "license"):
            i = bp.lower().find(key.lower())
            if i >= 0:
                saylor_snips.append(bp[max(0, i - 20) : i + 220])
        units = re.findall(r"Unit\s+\d+[^\n<]{0,100}", bus203.text)
        # Moodle activity links
        activities = re.findall(
            r'href="(https?://learn\.saylor\.org/mod/[^"]+)"[^>]*>([^<]{3,120})',
            bus203.text,
        )
        out["saylor_bus203"] = {
            "http": bus203.status_code,
            "final_url": str(bus203.url),
            "license_snippets": saylor_snips,
            "units_sample": units[:20],
            "activities_sample": [{"url": u, "title": t.strip()} for u, t in activities[:40]],
        }

        # Sample a few page resources for third-party markers
        page_urls = [u for u, _ in activities if "/mod/page/" in u][:8]
        page_probe = []
        for url in page_urls:
            r = client.get(url)
            pt = plain(r.text)
            markers = {
                "has_cc_by": bool(re.search(r"CC BY(?!-NC)|Attribution 3\.0|Attribution 4\.0", pt, re.I)),
                "has_nc": bool(re.search(r"NonCommercial|BY-NC|CC BY-NC", pt, re.I)),
                "mentions_third_party": bool(re.search(r"third[- ]party", pt, re.I)),
                "mentions_openstax": bool(re.search(r"OpenStax", pt, re.I)),
                "mentions_boundless": bool(re.search(r"Boundless", pt, re.I)),
                "mentions_lumen": bool(re.search(r"Lumen", pt, re.I)),
            }
            page_probe.append({"url": url, "http": r.status_code, "markers": markers, "title_snip": pt[:120]})
        out["page_probe"] = page_probe

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2)[:6000])


if __name__ == "__main__":
    main()
