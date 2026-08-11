"""Saylor Academy courses — CC BY 3.0 Saylor-authored content only (filtered).

Live-verified 2026-08-11 (course footers on learn.saylor.org):
"content authored by Saylor University is available under a Creative Commons
Attribution 3.0 Unported license. Third-party materials are the copyright of
their respective owners and shared under various licenses."

Guest-accessible inventory shows syllabi + chrome; unit readings require
enrollment. This fetcher:
1. Inventories page activities
2. Excludes NC / third-party / site-chrome / external URL resources
3. Ingests only course-specific Saylor-authored syllabus (and intro) pages
4. Emits include/exclude evidence for delivery audit
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.knowledge_fabric.registry import KnowledgeSourceSpec

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0)"}

SAYLOR_COURSES: tuple[tuple[str, int, str, tuple[str, ...]], ...] = (
    ("BUS203", 1250, "marketing", ("marketing_strategy", "segmentation", "promotion", "pricing")),
    ("BUS633", 881, "sales", ("personal_selling", "sales_management", "pipeline")),
    ("BUS630", 789, "marketing", ("consumer_behavior", "customer_value")),
    ("BUS631", 878, "marketing", ("brand_management", "positioning", "promotion")),
    ("BUS632", 1266, "marketing", ("digital_marketing", "advertising")),
    ("BUS634", 1278, "marketing", ("market_research", "marketing_strategy")),
    ("BUS502", 669, "marketing", ("marketing_strategy", "targeting", "positioning")),
    ("BUS615", 796, "marketing", ("international_marketing", "marketing_strategy")),
)


def _plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _guest_login(client: httpx.Client) -> None:
    login = client.get("https://learn.saylor.org/login/index.php")
    token = re.search(r'name="logintoken" value="([^"]+)"', login.text)
    if token:
        client.post(
            "https://learn.saylor.org/login/index.php",
            data={"logintoken": token.group(1), "loginguest": "1"},
        )


def classify_saylor_page(title: str, text: str, course_code: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    lower_title = (title or "").lower()
    if re.search(r"NonCommercial|BY-NC|CC BY-NC", text, re.I):
        reasons.append("nc_license_marker")
    if re.search(r"\bOpenStax\b|\bBoundless\b|\bLumen Learning\b|\bFlat World\b", text, re.I):
        reasons.append("third_party_publisher_marker")
    if re.search(r"adapted from|reused from|reproduced with permission", text, re.I):
        reasons.append("adaptation_marker")
    if "translation faqs" in lower_title or "certificate verification" in lower_title:
        reasons.append("site_chrome_not_course_content")
    if "ai learning zone" in lower_title:
        reasons.append("ai_zone_or_nc_risk")
    is_cc_by = bool(re.search(r"Creative Commons Attribution|CC BY 3\.0|CC BY 4\.0", text, re.I))
    course_specific = course_code.lower() in lower_title or course_code.lower() in text[:1500].lower()
    is_syllabus_or_intro = ("syllabus" in lower_title) or ("course introduction" in lower_title)
    include = (
        is_cc_by
        and course_specific
        and is_syllabus_or_intro
        and not reasons
        and 800 < len(text) < 80000
    )
    if not include and not reasons:
        if not is_syllabus_or_intro:
            reasons.append("not_syllabus_or_intro_guest_surface")
        elif not course_specific:
            reasons.append("not_course_specific")
        else:
            reasons.append("failed_include_heuristics")
    return include, reasons


def provenance_filter_course(client: httpx.Client, course_code: str, course_id: int) -> dict[str, Any]:
    course_url = f"https://learn.saylor.org/course/view.php?id={course_id}"
    r = client.get(course_url)
    page_ids = list(dict.fromkeys(re.findall(r"/mod/page/view\.php\?id=(\d+)", r.text)))
    url_ids = list(dict.fromkeys(re.findall(r"/mod/url/view\.php\?id=(\d+)", r.text)))
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for uid in url_ids:
        excluded.append(
            {
                "url": f"https://learn.saylor.org/mod/url/view.php?id={uid}",
                "title": "external_url_activity",
                "reasons": ["external_url_third_party_or_unverified"],
            }
        )

    for pid in page_ids:
        url = f"https://learn.saylor.org/mod/page/view.php?id={pid}"
        pr = client.get(url)
        text = _plain(pr.text)
        tm = re.search(r"<title>([^<]+)</title>", pr.text, re.I)
        title = (tm.group(1) if tm else pid).replace("| Saylor University", "").strip()
        include, reasons = classify_saylor_page(title, text, course_code)
        row = {"page_id": pid, "url": url, "title": title, "chars": len(text), "reasons": reasons}
        if include:
            # Trim to course body
            start = text.find(f"{course_code}:")
            if start < 0:
                start = text.lower().find("course syllabus")
            body = text[max(0, start) : max(0, start) + 9000] if start >= 0 else text[:9000]
            row["content"] = body
            included.append(row)
        else:
            excluded.append(row)

    # Honest note: guest surface does not expose unit readings
    excluded.append(
        {
            "url": course_url,
            "title": f"{course_code} unit readings (guest-inaccessible)",
            "reasons": [
                "unit_materials_require_enrollment_not_ingested",
                "third_party_materials_various_licenses_per_saylor_footer",
            ],
        }
    )
    return {
        "course_code": course_code,
        "course_id": course_id,
        "course_url": course_url,
        "included": included,
        "excluded": excluded,
        "included_count": len(included),
        "excluded_count": len(excluded),
    }


async def fetch_saylor_documents(
    spec: KnowledgeSourceSpec,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    # source_id like marketing.saylor.bus203
    code = (spec.source_id.split(".")[-1] or "").upper()
    match = next((c for c in SAYLOR_COURSES if c[0] == code), None)
    if not match:
        return []
    course_code, course_id, _dept, topics = match
    docs: list[dict[str, Any]] = []
    with httpx.Client(timeout=90, follow_redirects=True, headers=_HEADERS) as client:
        _guest_login(client)
        report = provenance_filter_course(client, course_code, course_id)
        for item in report["included"][:limit]:
            docs.append(
                {
                    "external_id": f"saylor-{course_code.lower()}-{item['page_id']}",
                    "title": item["title"],
                    "content": item["content"],
                    "citation": (
                        f"Saylor Academy {course_code} (CC BY 3.0 Saylor-authored) — {item['url']}"
                    ),
                    "jurisdiction": None,
                    "topics": list(topics),
                    "metadata": {
                        "license_type": "A",
                        "license": "CC-BY-3.0",
                        "provenance_filter": {
                            "included_count": report["included_count"],
                            "excluded_count": report["excluded_count"],
                            "excluded_sample": [
                                {"title": e.get("title"), "reasons": e.get("reasons")}
                                for e in report["excluded"][:8]
                            ],
                        },
                    },
                }
            )
    return docs


def provenance_report_all() -> dict[str, Any]:
    """CLI/audit helper — full include/exclude evidence for all targeted courses."""
    out: dict[str, Any] = {"courses": {}}
    with httpx.Client(timeout=90, follow_redirects=True, headers=_HEADERS) as client:
        _guest_login(client)
        for course_code, course_id, dept, topics in SAYLOR_COURSES:
            report = provenance_filter_course(client, course_code, course_id)
            report["department"] = dept
            report["topics"] = list(topics)
            # Drop bulky content from audit JSON
            for inc in report["included"]:
                inc.pop("content", None)
            out["courses"][course_code] = report
    return out
