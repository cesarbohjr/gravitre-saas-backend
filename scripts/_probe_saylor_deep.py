"""Deeper Saylor course structure probe — find unit/resource licensing."""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "GravitreKnowledgeFabric/1.0 (license-verify; support@gravitre.ai)"}
COURSES = {
    "BUS203": "https://learn.saylor.org/course/view.php?id=72",
    "BUS633": "https://learn.saylor.org/course/index.php?categoryid=2",  # will resolve
}
# Known course IDs from Saylor catalog search patterns
COURSE_SEARCH = [
    ("BUS203", "https://learn.saylor.org/course/search.php?search=BUS203"),
    ("BUS633", "https://learn.saylor.org/course/search.php?search=BUS633"),
    ("BUS630", "https://learn.saylor.org/course/search.php?search=BUS630"),
]


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def main() -> None:
    out: dict = {}
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        # Licensing detail page (footer link often 22068; try search)
        for label, url in [
            ("licensing_detail_22068", "https://learn.saylor.org/mod/page/view.php?id=22068"),
            ("opencontent", "https://www.saylor.org/books/"),
            ("terms", "https://www.saylor.org/terms-of-use/"),
            ("about_open", "https://www.saylor.org/about/"),
        ]:
            try:
                r = client.get(url)
                p = plain(r.text)
                snips = []
                for key in ("Creative Commons", "Third-party", "CC BY", "NonCommercial", "license"):
                    i = p.lower().find(key.lower())
                    if i >= 0:
                        snips.append(p[max(0, i - 30) : i + 200])
                out[label] = {"http": r.status_code, "url": str(r.url), "snips": snips[:4]}
            except Exception as exc:  # noqa: BLE001
                out[label] = {"error": str(exc)[:200]}

        for code, url in COURSE_SEARCH:
            r = client.get(url)
            # course links
            links = re.findall(
                r'href="(https://learn\.saylor\.org/course/view\.php\?id=\d+)"[^>]*>([^<]{0,120})',
                r.text,
            )
            if not links:
                links = re.findall(
                    r'href="(/course/view\.php\?id=\d+)"[^>]*>([^<]{0,120})',
                    r.text,
                )
                links = [("https://learn.saylor.org" + u, t) for u, t in links]
            out[f"search_{code}"] = {
                "http": r.status_code,
                "links": [{"url": u, "title": t.strip()} for u, t in links[:10]],
            }

        # BUS203 full HTML resource inventory
        r = client.get("https://learn.saylor.org/course/view.php?id=72")
        # Section headers
        sections = re.findall(
            r'id="section-\d+"[\s\S]{0,200}?class="sectionname"[^>]*>([^<]+)',
            r.text,
        )
        if not sections:
            sections = re.findall(r'class="sectionname"[^>]*>([^<]+)', r.text)
        # All mod links with surrounding text
        mods = re.findall(
            r'href="((?:https://learn\.saylor\.org)?/mod/(?:page|url|book|resource)/view\.php\?id=\d+)"[^>]*>\s*([^<]{2,160})',
            r.text,
        )
        normalized = []
        for u, t in mods:
            if u.startswith("/"):
                u = "https://learn.saylor.org" + u
            title = re.sub(r"\s+", " ", t).strip()
            if title and title not in {"Translate", "Verify Certificate"}:
                normalized.append({"url": u, "title": title})
        # dedupe
        seen = set()
        uniq = []
        for item in normalized:
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            uniq.append(item)
        out["bus203_inventory"] = {
            "sections": sections[:30],
            "resources": uniq[:80],
            "resource_count": len(uniq),
        }

        # Probe first 12 page resources for third-party / NC
        probes = []
        for item in uniq[:12]:
            if "/mod/page/" not in item["url"] and "/mod/book/" not in item["url"]:
                # URL resources — mark as external, need check
                probes.append({**item, "kind": "external_or_file", "skipped_body": True})
                continue
            pr = client.get(item["url"])
            pt = plain(pr.text)
            exclude_reasons = []
            if re.search(r"NonCommercial|BY-NC|CC BY-NC", pt, re.I):
                exclude_reasons.append("nc_license_marker")
            if re.search(r"OpenStax|Boundless|Lumen Learning|Saylor Foundation adapted|reused from", pt, re.I):
                exclude_reasons.append("third_party_publisher_marker")
            if re.search(r"All rights reserved", pt, re.I) and not re.search(r"Creative Commons Attribution", pt, re.I):
                exclude_reasons.append("all_rights_reserved_without_cc_by")
            # Saylor-authored framing often short unit intros
            is_cc_by = bool(re.search(r"Creative Commons Attribution|CC BY 3\.0|CC BY 4\.0", pt, re.I))
            probes.append(
                {
                    **item,
                    "http": pr.status_code,
                    "chars": len(pt),
                    "is_cc_by": is_cc_by,
                    "exclude_reasons": exclude_reasons,
                    "include_candidate": is_cc_by and not exclude_reasons,
                    "snip": pt[200:450] if len(pt) > 450 else pt[:250],
                }
            )
        out["bus203_resource_probes"] = probes

    Path("docs/delivery/saylor-deep-probe.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("sections", out.get("bus203_inventory", {}).get("sections"))
    print("resource_count", out.get("bus203_inventory", {}).get("resource_count"))
    for p in out.get("bus203_resource_probes", [])[:8]:
        print(p.get("title"), "include=", p.get("include_candidate"), "excl=", p.get("exclude_reasons"), "chars=", p.get("chars"))
    for k in out:
        if k.startswith("search_"):
            print(k, out[k])


if __name__ == "__main__":
    main()
