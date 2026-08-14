"""Self-enrol as guest where possible and inventory Saylor BUS course pages."""
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
    "BUS631": 878,
    "BUS632": 1266,
    "BUS634": 1278,
    "BUS502": 669,
    "BUS615": 796,
}


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def guest_login(client: httpx.Client) -> None:
    login = client.get("https://learn.saylor.org/login/index.php")
    token_m = re.search(r'name="logintoken" value="([^"]+)"', login.text)
    if not token_m:
        return
    client.post(
        "https://learn.saylor.org/login/index.php",
        data={"logintoken": token_m.group(1), "loginguest": "1"},
    )


def try_enrol(client: httpx.Client, course_id: int) -> dict:
    enrol_url = f"https://learn.saylor.org/enrol/index.php?id={course_id}"
    r = client.get(enrol_url)
    # self enrolment form
    sesskey = re.search(r'name="sesskey" value="([^"]+)"', r.text)
    instances = re.findall(r'name="instance" value="(\d+)"', r.text)
    result = {"enrol_http": r.status_code, "instances": instances, "has_sesskey": bool(sesskey)}
    if sesskey and instances:
        post = client.post(
            enrol_url,
            data={
                "id": str(course_id),
                "instance": instances[0],
                "sesskey": sesskey.group(1),
                "enrol": "1",
            },
        )
        result["post_http"] = post.status_code
        result["post_url"] = str(post.url)
    return result


def classify_page(title: str, pt: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if re.search(r"NonCommercial|BY-NC|CC BY-NC", pt, re.I):
        reasons.append("nc_license_marker")
    if re.search(r"\bOpenStax\b|\bBoundless\b|\bLumen Learning\b|\bFlat World\b", pt, re.I):
        reasons.append("third_party_publisher_marker")
    if re.search(r"adapted from|reused from|reproduced with permission", pt, re.I):
        reasons.append("adaptation_marker")
    if re.search(r"All rights reserved", pt, re.I) and not re.search(
        r"Creative Commons Attribution", pt, re.I
    ):
        reasons.append("all_rights_reserved_without_cc_by")
    is_cc_by = bool(re.search(r"Creative Commons Attribution|CC BY 3\.0|CC BY 4\.0", pt, re.I))
    # Exclude navigation chrome-only pages
    if title.lower() in {"translate", "verify certificate"} or "translation faqs" in pt.lower()[:800]:
        reasons.append("site_chrome_not_course_content")
    include = is_cc_by and not reasons and 500 < len(pt) < 80000
    if not include and not reasons:
        reasons.append("failed_include_heuristics")
    return include, reasons


def inventory(client: httpx.Client, code: str, course_id: int) -> dict:
    enrol = try_enrol(client, course_id)
    course_url = f"https://learn.saylor.org/course/view.php?id={course_id}"
    r = client.get(course_url)
    page_ids = list(dict.fromkeys(re.findall(r"/mod/page/view\.php\?id=(\d+)", r.text)))
    url_ids = list(dict.fromkeys(re.findall(r"/mod/url/view\.php\?id=(\d+)", r.text)))
    book_ids = list(dict.fromkeys(re.findall(r"/mod/book/view\.php\?id=(\d+)", r.text)))
    # titles near activity cards
    titles = re.findall(
        r'class="instancename"[^>]*>\s*([^<]+?)(?:\s*<span class="accesshide"|</)',
        r.text,
    )
    if not titles:
        titles = re.findall(r'class="aalink"[^>]*>\s*<span[^>]*class="instancename"[^>]*>([^<]+)', r.text)

    included = []
    excluded = []
    for pid in page_ids:
        url = f"https://learn.saylor.org/mod/page/view.php?id={pid}"
        pr = client.get(url)
        pt = plain(pr.text)
        # title from page
        tm = re.search(r"<title>([^<]+)</title>", pr.text, re.I)
        title = (tm.group(1) if tm else pid).replace("| Saylor University", "").strip()
        include, reasons = classify_page(title, pt)
        row = {
            "page_id": pid,
            "url": url,
            "title": title,
            "chars": len(pt),
            "reasons": reasons,
            "snip": pt[300:700],
        }
        if include:
            included.append(row)
        else:
            excluded.append(row)

    # External URL activities — always exclude from auto-ingest (license unknown)
    for uid in url_ids:
        excluded.append(
            {
                "page_id": uid,
                "url": f"https://learn.saylor.org/mod/url/view.php?id={uid}",
                "title": "external_url_activity",
                "reasons": ["external_url_third_party_or_unverified"],
            }
        )

    return {
        "course_id": course_id,
        "enrol": enrol,
        "http": r.status_code,
        "page_ids": page_ids,
        "url_ids": url_ids,
        "book_ids": book_ids,
        "instancenames_sample": titles[:40],
        "included": included,
        "excluded": excluded,
        "included_count": len(included),
        "excluded_count": len(excluded),
    }


def main() -> None:
    out = {"courses": {}}
    with httpx.Client(timeout=90, follow_redirects=True, headers=HEADERS) as client:
        guest_login(client)
        for code, cid in COURSES.items():
            print("course", code)
            out["courses"][code] = inventory(client, code, cid)
            c = out["courses"][code]
            print(
                " pages",
                len(c["page_ids"]),
                "urls",
                len(c["url_ids"]),
                "incl",
                c["included_count"],
                "excl",
                c["excluded_count"],
                "names",
                c["instancenames_sample"][:5],
            )

    path = Path("docs/delivery/saylor-provenance-filter-evidence.json")
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
