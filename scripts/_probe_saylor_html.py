"""Inspect why Saylor course pages show zero resources."""
from __future__ import annotations

import re
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GravitreKnowledgeFabric/1.0)"}


def main() -> None:
    with httpx.Client(timeout=60, follow_redirects=True, headers=HEADERS) as client:
        login = client.get("https://learn.saylor.org/login/index.php")
        token_m = re.search(r'name="logintoken" value="([^"]+)"', login.text)
        print("guest button", "guest" in login.text.lower(), "loginguest" in login.text.lower())
        if token_m:
            # Try Moodle guest button
            for payload in (
                {"logintoken": token_m.group(1), "username": "guest", "password": "guest"},
                {"logintoken": token_m.group(1), "loginguest": "1"},
            ):
                client.post("https://learn.saylor.org/login/index.php", data=payload)
        r = client.get("https://learn.saylor.org/course/view.php?id=1250")
        Path("docs/delivery/_bus203_1250.html").write_text(r.text, encoding="utf-8")
        print("status", r.status_code, "url", r.url, "len", len(r.text))
        for pat in (
            "enrol",
            "Enroll",
            "log in",
            "Login",
            "available as a guest",
            "sectionname",
            "activityinstance",
            "mod/page",
            "mod/url",
            "accessdenied",
            "not enrolled",
        ):
            print(pat, r.text.lower().count(pat.lower()) if pat.islower() else r.text.count(pat))
        # enrollment form?
        enrol = re.findall(r'enrol/index\.php\?id=\d+|enrol/self', r.text)
        print("enrol links", enrol[:10])
        snip_i = r.text.lower().find("enrol")
        if snip_i >= 0:
            print("enrol context:", re.sub(r"\s+", " ", r.text[snip_i : snip_i + 400]))


if __name__ == "__main__":
    main()
