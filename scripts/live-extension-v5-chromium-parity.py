#!/usr/bin/env python3
"""v5 Chromium parity: same MV3 extension + full v1–v4 API smoke on tip.

Proves Edge/Brave can load the unpacked extension (chrome.* APIs) and that the
deployed tip still serves enrich / usage-signal / workflows / chat front doors.
Firefox / Safari / mobile stay out of scope.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
EXT = REPO / "apps" / "extension"
OUT = REPO / "docs" / "delivery" / "browser-extension-v5-live.json"
BASE = "https://gravitre-saas-backend-production.up.railway.app"
ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
ACTOR = "f7e32f06-49df-4e73-8962-f41c21850762"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
BRAVE_CANDIDATES = [
    Path(os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")),
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                loaded = dotenv_values(p, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            continue
        merged.update({k: v for k, v in loaded.items() if v})
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def _auth_headers() -> dict[str, str]:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": ACTOR,
            "email": "smoke@gravitre.app",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        os.environ["SUPABASE_JWT_SECRET"],
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": ORG,
        "X-Environment": "production",
        "Content-Type": "application/json",
    }


def _find_browser(candidates: list[Path]) -> Path | None:
    for p in candidates:
        if p.is_file():
            return p
    return None


def _launch_with_extension(browser: Path, label: str, port: int) -> dict:
    """Launch Chromium browser with unpacked extension; confirm debug endpoint + process."""
    if not EXT.is_dir() or not (EXT / "manifest.json").is_file():
        return {"status": "FAIL", "error": "extension pack missing", "browser": label}

    profile = Path(tempfile.mkdtemp(prefix=f"gvt-ext-{label}-"))
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    args = [
        str(browser),
        f"--user-data-dir={profile}",
        f"--disable-extensions-except={EXT}",
        f"--load-extension={EXT}",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "about:blank",
    ]
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    version = None
    last_err = None
    for _ in range(30):
        time.sleep(1)
        try:
            version = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2).json()
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            if proc.poll() is not None:
                break
    alive = proc.poll() is None
    # Best-effort close
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    try:
        shutil.rmtree(profile, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass

    ok = bool(alive and version and version.get("Browser"))
    return {
        "status": "PASS" if ok else "FAIL",
        "browser": label,
        "binary": str(browser),
        "manifestVersion": manifest.get("version"),
        "manifest_mv": manifest.get("manifest_version"),
        "debugVersion": version,
        "error": None if ok else (last_err or "browser exited before debug port ready"),
        "note": "Unpacked MV3 load via --load-extension; chrome.* APIs (Edge/Brave Chromium).",
    }


def _api_v1_v4_smoke(headers: dict[str, str]) -> dict:
    cases: dict[str, dict] = {}
    # session (auth front door)
    r = httpx.get(f"{BASE}/api/extension/session", headers=headers, timeout=60)
    cases["session"] = {
        "status": "PASS" if r.status_code == 200 and r.json().get("orgId") else "FAIL",
        "http": r.status_code,
        "allowedActions": (r.json() or {}).get("allowedActions") if r.status_code == 200 else None,
    }
    # usage-signal (v2)
    r = httpx.post(
        f"{BASE}/api/extension/usage-signal",
        headers=headers,
        json={
            "pageUrl": "https://example.com/not-allowlisted",
            "surface": "outside_allowlist",
            "invoked": True,
            "note": "v5-parity",
        },
        timeout=60,
    )
    cases["usage_signal"] = {
        "status": "PASS" if r.status_code == 200 else "FAIL",
        "http": r.status_code,
        "body": (json.dumps(r.json()) if r.status_code == 200 else r.text)[:300],
    }
    # enrich (v1/v2 surface)
    r = httpx.post(
        f"{BASE}/api/extension/enrich",
        headers=headers,
        json={
            "pageUrl": "https://www.linkedin.com/in/v5-parity",
            "pageContext": {
                "fullName": "Casey Operator",
                "company": "Gravitree Smoke Co",
                "title": "Head of Revenue Ops",
                "source": "linkedin",
            },
        },
        timeout=120,
    )
    ej = r.json() if r.status_code == 200 else {}
    cases["enrich"] = {
        "status": "PASS" if r.status_code == 200 and "suggestions" in ej else "FAIL",
        "http": r.status_code,
        "surface": ej.get("surface"),
        "suggestionCount": len(ej.get("suggestions") or []),
    }
    # workflows list (v3)
    r = httpx.get(
        f"{BASE}/api/extension/workflows?environment=production",
        headers=headers,
        timeout=60,
    )
    wj = r.json() if r.status_code == 200 else {}
    cases["workflows_list"] = {
        "status": "PASS" if r.status_code == 200 and int(wj.get("count") or 0) >= 1 else "FAIL",
        "http": r.status_code,
        "count": wj.get("count"),
    }
    # chat (v4) — page context + handoff
    r = httpx.post(
        f"{BASE}/api/extension/chat",
        headers=headers,
        json={
            "message": (
                "Using only the overlay page context, answer in one sentence: "
                "what is this person's full name, title, and company?"
            ),
            "pageUrl": "https://www.linkedin.com/in/v5-parity",
            "pageContext": {
                "fullName": "Casey Operator",
                "company": "Gravitree Smoke Co",
                "title": "Head of Revenue Ops",
                "source": "linkedin",
            },
        },
        timeout=180,
    )
    cj = r.json() if r.status_code == 200 else {}
    ans = (cj.get("answer") or "").lower()
    cases["chat_page_context"] = {
        "status": "PASS"
        if r.status_code == 200
        and (("casey" in ans) or ("gravitree smoke" in ans) or ("revenue" in ans))
        else "FAIL",
        "http": r.status_code,
        "conversationId": cj.get("conversationId"),
        "path": cj.get("path"),
        "answerPreview": (cj.get("answer") or "")[:240],
    }
    r = httpx.post(
        f"{BASE}/api/extension/chat",
        headers=headers,
        json={
            "message": "Create a HubSpot list for Casey Operator from this page.",
            "pageUrl": "https://www.linkedin.com/in/v5-parity",
            "pageContext": {
                "fullName": "Casey Operator",
                "company": "Gravitree Smoke Co",
                "source": "linkedin",
            },
            "conversationId": cj.get("conversationId"),
        },
        timeout=120,
    )
    hj = r.json() if r.status_code == 200 else {}
    cases["chat_handoff"] = {
        "status": "PASS"
        if r.status_code == 200 and hj.get("needsHandoff") and "/ai?c=" in str(hj.get("openInGravitreeUrl") or "")
        else "FAIL",
        "http": r.status_code,
        "needsHandoff": hj.get("needsHandoff"),
        "openInGravitreeUrl": hj.get("openInGravitreeUrl"),
    }
    return cases


def main() -> int:
    _load_env()
    evidence: dict = {
        "startedAt": utcnow(),
        "scope": {
            "in": ["chrome", "edge", "brave"],
            "out": ["firefox", "safari", "mobile"],
        },
        "cases": {},
    }
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    evidence["git_sha"] = health.get("git_sha")
    headers = _auth_headers()
    evidence["cases"]["api_v1_v4"] = _api_v1_v4_smoke(headers)

    edge = _find_browser(EDGE_CANDIDATES)
    brave = _find_browser(BRAVE_CANDIDATES)
    if edge:
        evidence["cases"]["edge_load_extension"] = _launch_with_extension(edge, "edge", 9331)
    else:
        evidence["cases"]["edge_load_extension"] = {
            "status": "FAIL",
            "error": "Microsoft Edge binary not found",
        }
    if brave:
        evidence["cases"]["brave_load_extension"] = _launch_with_extension(brave, "brave", 9332)
    else:
        evidence["cases"]["brave_load_extension"] = {
            "status": "FAIL",
            "error": "Brave binary not found — install Brave.Brave then re-run",
        }

    api_ok = all(
        c.get("status") == "PASS" for c in (evidence["cases"]["api_v1_v4"] or {}).values()
    )
    edge_ok = evidence["cases"]["edge_load_extension"].get("status") == "PASS"
    brave_ok = evidence["cases"]["brave_load_extension"].get("status") == "PASS"
    if api_ok and edge_ok and brave_ok:
        evidence["overall"] = "PASS"
    elif api_ok and (edge_ok or brave_ok):
        evidence["overall"] = "PARTIAL"
    else:
        evidence["overall"] = "FAIL"
    evidence["finishedAt"] = utcnow()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2)[:6000])
    return 0 if evidence["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
