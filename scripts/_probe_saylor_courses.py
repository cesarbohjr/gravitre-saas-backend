"""Inventory Saylor marketing/sales courses with provenance markers."""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0)"}
COURSES = {
    "BUS203": 1250,
    "BUS633": 881,
    "BUS630": 789,
    "BUS631": None,
    "BUS632": None,
    "BUS634": None,
    "BUS502": None,
    "BUS615": None,
}


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def resolve_ids(client: httpx.Client) -> None:
    for code in list(COURSES):
        if COURSES[code] is not None:
            continue
        r = client.get("https://learn.saylor.org/course/search.php", params={"search": code})
        ids = list(dict.fromkeys(re.findall(r"course/view\.php\?id=(\d+)", r.text)))
        titles = re.findall(r"BUS\d+:\s*[^<]{3,80}", r.text)
        COURSES[code] = int(ids[0]) if ids else None
        print(code, "->", COURSES[code], titles[:2])


def guest_login(client: httpx.Client) -> None:
    r = client.get("https://learn.saylor.org/login/index.php")
    m = re.search(r'name="logintoken" value="([^"]+)"', r.text)
    if not m:
        print("no logintoken")
        return
    client.post(
        "https://learn.saylor.org/login/index.php",
        data={"logintoken": m.group(1), "username": "guest", "password": "guest"},
    )


def inventory_course(client: httpx.Client, code: str, course_id: int) -> dict:
    url = f"https://learn.saylor.org/course/view.php?id={course_id}"
    r = client.get(url)
    sections = re.findall(r'class="sectionname"[^>]*>([^<]+)', r.text)
    mods = re.findall(
        r'href="((?:https://learn\.saylor\.org)?/mod/(?:page|url|book|resource|folder)/view\.php\?id=\d+)[^"]*"'
        r"[^>]*>\s*([^<]{2,160})",
        r.text,
    )
    resources = []
    seen = set()
    for u, t in mods:
        if u.startswith("/"):
            u = "https://learn.saylor.org" + u
        title = re.sub(r"\s+", " ", t).strip()
        if not title or "Translate" in title or "Verify Certificate" in title:
            continue
        if u in seen:
            continue
        seen.add(u)
        resources.append({"url": u, "title": title})

    probes = []
    included = []
    excluded = []
    for item in resources[:40]:
        kind = "page" if "/mod/page/" in item["url"] or "/mod/book/" in item["url"] else "external"
        if kind != "page":
            excluded.append({**item, "reasons": ["non_page_resource_needs_manual_license_check"]})
            continue
        pr = client.get(item["url"])
        pt = plain(pr.text)
        reasons = []
        if re.search(r"NonCommercial|BY-NC|CC BY-NC", pt, re.I):
            reasons.append("nc_license_marker")
        if re.search(
            r"OpenStax|Boundless|Lumen Learning|Flat World|All rights reserved(?![^.]{0,40}Creative Commons)",
            pt,
            re.I,
        ):
            reasons.append("third_party_publisher_marker")
        if re.search(r"adapted from|reused from|reproduced from", pt, re.I):
            reasons.append("adaptation_marker")
        is_cc_by = bool(re.search(r"Creative Commons Attribution|CC BY 3\.0|CC BY 4\.0", pt, re.I))
        # Prefer short Saylor framing pages (unit intros / syllabi), not long third-party dumps
        bodyish = pt
        for noise in ("Skip to main content", "Side panel", "Courses & Programs"):
            bodyish = bodyish.replace(noise, "")
        record = {
            **item,
            "http": pr.status_code,
            "chars": len(pt),
            "is_cc_by": is_cc_by,
            "reasons": reasons,
        }
        probes.append(record)
        if is_cc_by and not reasons and 400 < len(pt) < 25000:
            included.append(record)
        else:
            if not reasons:
                reasons = ["failed_include_heuristics"]
            excluded.append({**record, "reasons": reasons})

    return {
        "course_id": course_id,
        "url": url,
        "http": r.status_code,
        "sections": sections[:40],
        "resource_count": len(resources),
        "resources_sample": resources[:25],
        "included": included,
        "excluded_sample": excluded[:25],
        "included_count": len(included),
        "excluded_count": len(excluded),
        "probes_sample": probes[:15],
    }


def main() -> None:
    out: dict = {"courses": {}}
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        guest_login(client)
        resolve_ids(client)
        out["resolved_ids"] = {k: v for k, v in COURSES.items()}
        for code, cid in COURSES.items():
            if cid is None:
                out["courses"][code] = {"error": "course_id_not_found"}
                continue
            print("inventory", code, cid)
            out["courses"][code] = inventory_course(client, code, cid)
            print(
                " ",
                "sections",
                len(out["courses"][code].get("sections") or []),
                "resources",
                out["courses"][code].get("resource_count"),
                "included",
                out["courses"][code].get("included_count"),
            )

    Path("docs/delivery/saylor-provenance-probe.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print("wrote docs/delivery/saylor-provenance-probe.json")


if __name__ == "__main__":
    main()
