"""Extract Saylor-authored syllabus text for courses we can access as guest."""
from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0)"}
# Course-specific syllabus page ids from live guest inventory (2026-08-11)
SYLLABI = {
    "BUS203": ("1250", "89302"),
    "BUS633": ("881", "83120"),
    "BUS630": ("789", "71941"),
    "BUS631": ("878", "83091"),  # may need confirm
    "BUS632": ("1266", None),
    "BUS634": ("1278", None),
    "BUS502": ("669", None),
    "BUS615": ("796", None),
}


def plain(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> None:
    evidence = json.loads(Path("docs/delivery/saylor-provenance-filter-evidence.json").read_text(encoding="utf-8"))
    # refresh syllabus ids from evidence
    for code, course in evidence.get("courses", {}).items():
        for inc in course.get("included", []):
            if "Syllabus" in (inc.get("title") or ""):
                SYLLABI[code] = (str(course["course_id"]), str(inc["page_id"]))

    out = {}
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        login = client.get("https://learn.saylor.org/login/index.php")
        token = re.search(r'name="logintoken" value="([^"]+)"', login.text)
        if token:
            client.post(
                "https://learn.saylor.org/login/index.php",
                data={"logintoken": token.group(1), "loginguest": "1"},
            )
        for code, (cid, pid) in SYLLABI.items():
            if not pid:
                out[code] = {"status": "no_syllabus_page_id"}
                continue
            url = f"https://learn.saylor.org/mod/page/view.php?id={pid}"
            r = client.get(url)
            text = plain(r.text)
            # Find body after course title
            start = text.find(f"{code}:")
            if start < 0:
                start = text.find("Course Syllabus")
            body = text[start : start + 9000] if start >= 0 else text[:9000]
            third_party = bool(
                re.search(r"OpenStax|Boundless|Lumen|NonCommercial|BY-NC", body, re.I)
            )
            out[code] = {
                "course_id": cid,
                "page_id": pid,
                "url": url,
                "http": r.status_code,
                "chars": len(body),
                "third_party_markers_in_syllabus": third_party,
                "preview": body[:600],
            }
            print(code, "chars", len(body), "3p", third_party)

    Path("docs/delivery/saylor-syllabi-extract.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
