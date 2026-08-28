"""Is the three-state verification label actually live in the deployed web bundle?

The backend projection and the UI ship on separate deploys, so a green Railway
git_sha says nothing about whether users stopped seeing "Verified" on an
unproven write. Preloaded chunks alone are not enough — the outcome card is
code-split behind authenticated routes — so enumerate the build manifests and
scan every chunk they name.
"""
from __future__ import annotations

import json
import re
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://gravitre.app"
PAGES = ["/health", "/login", "/ai", "/activity"]
MARKERS = ("accepted_unproven", "Accepted \u2014 not yet confirmed", "not yet confirmed")
# Present in the committed component today; if the deploy is fresh this must be
# there, so its absence means the scan cannot see the component at all.
CONTROL = "Flagged for review"


def main() -> int:
    client = httpx.Client(timeout=30, follow_redirects=True)
    chunks: set[str] = set()
    build_ids: set[str] = set()

    for page in PAGES:
        try:
            r = client.get(BASE + page)
        except Exception as exc:  # noqa: BLE001
            print(f"{page}: fetch failed {exc}")
            continue
        chunks.update(re.findall(r'/_next/static/[^"\'\\ ]+?\.js', r.text))
        build_ids.update(re.findall(r'/_next/static/([^/"]+)/_buildManifest\.js', r.text))
        build_ids.update(re.findall(r'"buildId"\s*:\s*"([^"]+)"', r.text))
        print(f"{page}: {r.status_code}")

    print(f"build ids: {sorted(build_ids) or '<none>'}")

    for manifest in ("/_next/app-build-manifest.json", "/_next/build-manifest.json"):
        try:
            r = client.get(BASE + manifest)
            if r.status_code == 200:
                chunks.update(re.findall(r'static/[^"\\ ]+?\.js', r.text))
                print(f"{manifest}: 200 (+chunks)")
        except Exception:  # noqa: BLE001
            pass

    for bid in build_ids:
        for name in ("_buildManifest.js", "_ssgManifest.js"):
            try:
                r = client.get(f"{BASE}/_next/static/{bid}/{name}")
                if r.status_code == 200:
                    chunks.update(re.findall(r'static/[^"\'\\ ]+?\.js', r.text))
                    print(f"{bid}/{name}: 200 (+chunks)")
            except Exception:  # noqa: BLE001
                pass

    normalized = {c if c.startswith("/") else "/_next/" + c for c in chunks}
    print(f"\nunique chunks: {len(normalized)}")

    hits: list[str] = []
    control_hits: list[str] = []
    scanned = 0
    for path in sorted(normalized):
        try:
            body = client.get(BASE + path).text
        except Exception:  # noqa: BLE001
            continue
        scanned += 1
        if CONTROL in body:
            control_hits.append(path)
        for marker in MARKERS:
            if marker in body:
                hits.append(f"{marker!r} in {path}")

    print(f"scanned: {scanned}")
    print(f"control {CONTROL!r} found in: {control_hits or '<none>'}")

    if hits:
        print("\nFOUND:")
        for h in hits:
            print("  ", h)
        print("\nRESULT: PASS - new label present in deployed bundle")
        return 0
    if not control_hits:
        print(
            "\nRESULT: INCONCLUSIVE - the outcome component was not reachable in any "
            "scanned chunk, so this says nothing about whether the fix deployed."
        )
        return 2
    print(
        "\nRESULT: FAIL - component chunk is present but still lacks the new label; "
        "the web layer has not picked up the fix."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
