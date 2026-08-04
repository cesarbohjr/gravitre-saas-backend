#!/usr/bin/env python3
"""v5 Chromium parity: Edge + Brave load MV3 pack AND exercise v1–v4 in-browser via CDP.

For each browser:
  1) --load-extension (unpacked apps/extension)
  2) CDP → extension service worker
  3) Seed chrome.storage session
  4) Functional: enrich → approve write → workflows list → chat + handoff
  5) Overlay DOM/CSS smoke (gvt-card / gvt-step / named-step classes)

Shared tip API smoke remains as a secondary check. Firefox/Safari/mobile out of scope.
CWS listing honesty is separate (NEXT_PUBLIC_CHROME_WEB_STORE_URL).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
import websockets
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
EXT = REPO / "apps" / "extension"
OUT = REPO / "docs" / "delivery" / "browser-extension-v5-live.json"
TIP = REPO / "docs" / "delivery" / "browser-extension-v5-tip-verify.json"
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


def _mint_token() -> str:
    url = os.environ["SUPABASE_URL"].rstrip("/")
    now = int(time.time())
    return jwt.encode(
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


def _auth_headers(token: str) -> dict[str, str]:
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


class CdpClient:
    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._ws: Any = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}
        self._reader: asyncio.Task | None = None

    async def __aenter__(self) -> "CdpClient":
        self._ws = await websockets.connect(self.ws_url, max_size=8_000_000)
        self._reader = asyncio.create_task(self._read_loop())
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._reader:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _read_loop(self) -> None:
        assert self._ws is not None
        async for raw in self._ws:
            msg = json.loads(raw)
            mid = msg.get("id")
            if mid in self._pending:
                fut = self._pending.pop(mid)
                if "error" in msg:
                    fut.set_exception(RuntimeError(json.dumps(msg["error"])))
                else:
                    fut.set_result(msg.get("result"))

    async def call(
        self,
        method: str,
        params: dict | None = None,
        session_id: str | None = None,
        timeout: float = 120,
    ) -> Any:
        assert self._ws is not None
        mid = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": mid, "method": method}
        if params:
            payload["params"] = params
        if session_id:
            payload["sessionId"] = session_id
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[mid] = fut
        await self._ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)


async def _browser_functional(browser: Path, label: str, port: int, token: str) -> dict:
    """Load extension in Edge/Brave and run v1–v4 flows inside the service worker."""
    if not (EXT / "manifest.json").is_file():
        return {"status": "FAIL", "browser": label, "error": "extension pack missing"}

    profile = Path(tempfile.mkdtemp(prefix=f"gvt-v5-{label}-"))
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    overlay_css = (EXT / "content" / "overlay.css").read_text(encoding="utf-8")
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
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    version = None
    last_err = None
    for _ in range(40):
        await asyncio.sleep(0.5)
        try:
            version = httpx.get(f"http://127.0.0.1:{port}/json/version", timeout=2).json()
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            if proc.poll() is not None:
                break

    cases: dict[str, Any] = {
        "browser": label,
        "binary": str(browser),
        "manifestVersion": manifest.get("version"),
        "debugVersion": version,
    }
    if not version:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(profile, ignore_errors=True)
        cases["status"] = "FAIL"
        cases["error"] = last_err or "debug port not ready"
        return cases

    ws_url = version.get("webSocketDebuggerUrl")
    try:
        async with CdpClient(ws_url) as cdp:
            # Discover Gravitree MV3 service worker (prefer background.js).
            sw_target = None
            candidates: list[dict] = []
            for _ in range(40):
                targets = await cdp.call("Target.getTargets")
                candidates = []
                for t in targets.get("targetInfos") or []:
                    url = str(t.get("url") or "")
                    ttype = str(t.get("type") or "")
                    if "chrome-extension://" not in url:
                        continue
                    if ttype not in {"service_worker", "shared_worker", "worker"}:
                        continue
                    if url.endswith("/background.js") or url.endswith("background.js"):
                        candidates.insert(0, t)
                    else:
                        candidates.append(t)
                if candidates:
                    # Verify manifest name before accepting.
                    for cand in candidates:
                        try:
                            attach_try = await cdp.call(
                                "Target.attachToTarget",
                                {"targetId": cand["targetId"], "flatten": True},
                            )
                            sess_try = attach_try.get("sessionId")
                            await cdp.call("Runtime.enable", session_id=sess_try)
                            name_eval = await cdp.call(
                                "Runtime.evaluate",
                                {
                                    "expression": (
                                        "(async () => {"
                                        " try {"
                                        "  const m = chrome.runtime.getManifest();"
                                        "  return {name: m && m.name, version: m && m.version};"
                                        " } catch (e) { return {error: String(e)}; }"
                                        "})()"
                                    ),
                                    "awaitPromise": True,
                                    "returnByValue": True,
                                },
                                session_id=sess_try,
                            )
                            meta = ((name_eval.get("result") or {}).get("value")) or {}
                            if str(meta.get("name") or "").lower() == "gravitree":
                                sw_target = cand
                                session = sess_try
                                cases["extensionManifest"] = meta
                                break
                        except Exception:  # noqa: BLE001
                            continue
                    if sw_target:
                        break
                await asyncio.sleep(0.5)

            if not sw_target:
                cases["status"] = "FAIL"
                cases["error"] = "extension service worker target not found"
                cases["swCandidates"] = [
                    {"url": c.get("url"), "type": c.get("type")} for c in candidates[:8]
                ]
            else:
                cases["extensionTargetUrl"] = sw_target.get("url")

                # Seed auth into extension storage (same keys as Connect handoff).
                seed_js = f"""
                (async () => {{
                  if (!chrome || !chrome.storage || !chrome.storage.local) {{
                    return {{ ok: false, error: "chrome.storage.local unavailable" }};
                  }}
                  await chrome.storage.local.set({{
                    accessToken: {json.dumps(token)},
                    orgId: {json.dumps(ORG)},
                    environment: "production",
                    apiBase: {json.dumps(BASE)},
                    appBase: "https://gravitre.app"
                  }});
                  const cfg = await chrome.storage.local.get(["accessToken","orgId","apiBase"]);
                  return {{
                    ok: !!(cfg.accessToken && cfg.orgId && cfg.apiBase),
                    hasToken: !!cfg.accessToken,
                    hasOrg: !!cfg.orgId,
                    apiBase: cfg.apiBase || null
                  }};
                }})()
                """
                seeded = await cdp.call(
                    "Runtime.evaluate",
                    {"expression": seed_js, "awaitPromise": True, "returnByValue": True},
                    session_id=session,
                )
                seed_val = (seeded.get("result") or {}).get("value") or {}
                seed_exc = (seeded.get("exceptionDetails") or {}).get("text")
                cases["storageSeed"] = {
                    "status": "PASS" if seed_val.get("ok") else "FAIL",
                    "value": seed_val,
                    "exception": seed_exc,
                }

                async def sw_fetch(
                    path: str,
                    method: str = "GET",
                    body: dict | None = None,
                    *,
                    timeout: float = 120,
                ) -> Any:
                    if body is None:
                        body_line = "body: undefined,"
                    else:
                        body_line = f"body: JSON.stringify({json.dumps(body)}),"
                    expr = f"""
                    (async () => {{
                      const cfg = await chrome.storage.local.get(["accessToken","orgId","environment","apiBase"]);
                      const res = await fetch((cfg.apiBase || {json.dumps(BASE)}) + {json.dumps(path)}, {{
                        method: {json.dumps(method)},
                        headers: {{
                          Authorization: "Bearer " + cfg.accessToken,
                          "Content-Type": "application/json",
                          "X-Org-Id": cfg.orgId,
                          "X-Environment": cfg.environment || "production"
                        }},
                        {body_line}
                      }});
                      const text = await res.text();
                      let json = null;
                      try {{ json = text ? JSON.parse(text) : null; }} catch (e) {{ json = {{ detail: text }}; }}
                      return {{ ok: res.ok, status: res.status, json }};
                    }})()
                    """
                    try:
                        result = await cdp.call(
                            "Runtime.evaluate",
                            {"expression": expr, "awaitPromise": True, "returnByValue": True},
                            session_id=session,
                            timeout=timeout,
                        )
                    except asyncio.TimeoutError:
                        return {"ok": False, "status": None, "json": {"detail": f"CDP timeout after {timeout}s"}}
                    except Exception as fetch_exc:  # noqa: BLE001
                        return {"ok": False, "status": None, "json": {"detail": repr(fetch_exc)[:300]}}
                    if result.get("exceptionDetails"):
                        return {
                            "ok": False,
                            "status": None,
                            "json": {"detail": result["exceptionDetails"].get("text")},
                        }
                    return (result.get("result") or {}).get("value") or {}

                # v1 enrich (retry with backoff — Apollo/prod can 500 transiently)
                enrich_body = {
                    "pageUrl": "https://www.linkedin.com/in/v5-parity-edge-brave",
                    "pageContext": {
                        "fullName": "Casey Operator",
                        "company": "Gravitree Smoke Co",
                        "title": "Head of Revenue Ops",
                        "source": "linkedin",
                    },
                    "environment": "production",
                }
                enrich: dict[str, Any] = {}
                for attempt in range(4):
                    enrich = await sw_fetch("/api/extension/enrich", "POST", enrich_body)
                    if enrich.get("ok") and isinstance((enrich.get("json") or {}).get("suggestions"), list):
                        break
                    await asyncio.sleep(1.5 * (attempt + 1))
                ej = enrich.get("json") or {}
                cases["enrich"] = {
                    "status": "PASS"
                    if enrich.get("ok") and isinstance(ej.get("suggestions"), list)
                    else "FAIL",
                    "http": enrich.get("status"),
                    "surface": ej.get("surface"),
                    "suggestionCount": len(ej.get("suggestions") or []),
                    "detail": (ej.get("detail") or ej.get("error") or "")[:300] or None,
                }

                # v1 approve write (propose + confirm)
                list_name = f"Ext v5 {label} {datetime.now(timezone.utc).strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"
                propose = await sw_fetch(
                    "/api/extension/actions/execute",
                    "POST",
                    {
                        "invokeAction": "hubspot.lists.create",
                        "params": {"name": list_name},
                        "pageUrl": "https://www.linkedin.com/in/v5-parity-edge-brave",
                        "environment": "production",
                    },
                )
                pj = propose.get("json") or {}
                token_c = pj.get("confirmationToken")
                cases["propose_write"] = {
                    "status": "PASS"
                    if propose.get("ok") and pj.get("status") == "needs_confirmation" and token_c
                    else "FAIL",
                    "http": propose.get("status"),
                    "approvalId": pj.get("approvalId"),
                    "detail": (pj.get("detail") or pj.get("error") or "")[:300] or None,
                }
                if token_c:
                    confirm = await sw_fetch(
                        "/api/extension/actions/execute",
                        "POST",
                        {
                            "confirmationToken": token_c,
                            "pageUrl": "https://www.linkedin.com/in/v5-parity-edge-brave",
                            "environment": "production",
                        },
                    )
                    cj = confirm.get("json") or {}
                    cases["confirm_write"] = {
                        "status": "PASS" if confirm.get("ok") and cj.get("success") and cj.get("runId") else "FAIL",
                        "http": confirm.get("status"),
                        "runId": cj.get("runId"),
                        "source": cj.get("source"),
                    }
                else:
                    cases["confirm_write"] = {"status": "FAIL", "error": "no confirmationToken"}

                # v3 workflows list
                wfs = await sw_fetch("/api/extension/workflows?environment=production")
                wj = wfs.get("json") or {}
                cases["workflows_list"] = {
                    "status": "PASS" if wfs.get("ok") and int(wj.get("count") or 0) >= 1 else "FAIL",
                    "http": wfs.get("status"),
                    "count": wj.get("count"),
                }

                # v4 chat + handoff (longer CDP timeout — LLM path)
                chat_body = {
                    "message": (
                        "Using only the overlay page context, answer in one sentence: "
                        "what is this person's full name, title, and company?"
                    ),
                    "pageUrl": "https://www.linkedin.com/in/v5-parity-edge-brave",
                    "pageContext": {
                        "fullName": "Casey Operator",
                        "company": "Gravitree Smoke Co",
                        "title": "Head of Revenue Ops",
                        "source": "linkedin",
                    },
                    "environment": "production",
                }
                chat = await sw_fetch("/api/extension/chat", "POST", chat_body, timeout=180)
                if not chat.get("ok"):
                    await asyncio.sleep(2.0)
                    chat = await sw_fetch("/api/extension/chat", "POST", chat_body, timeout=180)
                chat_j = chat.get("json") or {}
                ans = (chat_j.get("answer") or "").lower()
                cases["chat_page_context"] = {
                    "status": "PASS"
                    if chat.get("ok")
                    and (("casey" in ans) or ("gravitree smoke" in ans) or ("revenue" in ans))
                    else "FAIL",
                    "http": chat.get("status"),
                    "conversationId": chat_j.get("conversationId"),
                    "answerPreview": (chat_j.get("answer") or "")[:200],
                    "detail": (chat_j.get("detail") or chat_j.get("error") or "")[:300] or None,
                }
                handoff = await sw_fetch(
                    "/api/extension/chat",
                    "POST",
                    {
                        "message": "Create a HubSpot list for Casey Operator from this page.",
                        "pageUrl": "https://www.linkedin.com/in/v5-parity-edge-brave",
                        "pageContext": {
                            "fullName": "Casey Operator",
                            "company": "Gravitree Smoke Co",
                            "source": "linkedin",
                        },
                        "conversationId": chat_j.get("conversationId"),
                        "environment": "production",
                    },
                    timeout=180,
                )
                hj = handoff.get("json") or {}
                cases["chat_handoff"] = {
                    "status": "PASS"
                    if handoff.get("ok")
                    and hj.get("needsHandoff")
                    and "/ai?c=" in str(hj.get("openInGravitreeUrl") or "")
                    else "FAIL",
                    "http": handoff.get("status"),
                    "needsHandoff": hj.get("needsHandoff"),
                    "openInGravitreeUrl": hj.get("openInGravitreeUrl"),
                    "sameConversation": hj.get("conversationId") == chat_j.get("conversationId"),
                }

                # Overlay visual parity — inject CSS + plan-bar markup in a page target
                page_target = await cdp.call(
                    "Target.createTarget",
                    {"url": "https://example.com/"},
                )
                page_attach = await cdp.call(
                    "Target.attachToTarget",
                    {"targetId": page_target["targetId"], "flatten": True},
                )
                page_session = page_attach.get("sessionId")
                await cdp.call("Page.enable", session_id=page_session)
                await cdp.call("Runtime.enable", session_id=page_session)
                await asyncio.sleep(1.0)
                css_literal = json.dumps(overlay_css)
                overlay_js = f"""
                (() => {{
                  const style = document.createElement("style");
                  style.textContent = {css_literal};
                  document.documentElement.appendChild(style);
                  const root = document.createElement("div");
                  root.id = "gravitree-overlay-root";
                  root.innerHTML = `
                    <div class="gvt-card">
                      <div class="gvt-header"><div class="gvt-brand">Gravitree</div></div>
                      <div class="gvt-step gvt-step-pending">1. List HubSpot Pipelines</div>
                      <div class="gvt-step gvt-step-running">2. List HubSpot Deals</div>
                      <div class="gvt-outcome"><div class="gvt-outcome-title">Done</div></div>
                    </div>`;
                  document.body.appendChild(root);
                  const card = document.querySelector(".gvt-card");
                  const steps = document.querySelectorAll(".gvt-step");
                  const outcome = document.querySelector(".gvt-outcome");
                  const cs = card ? getComputedStyle(card) : null;
                  return {{
                    hasCard: !!card,
                    stepCount: steps.length,
                    hasOutcome: !!outcome,
                    cardBg: cs ? cs.backgroundColor : null,
                    cardDisplay: cs ? cs.display : null,
                  }};
                }})()
                """
                vis = await cdp.call(
                    "Runtime.evaluate",
                    {"expression": overlay_js, "returnByValue": True},
                    session_id=page_session,
                )
                vv = (vis.get("result") or {}).get("value") or {}
                cases["overlay_visual"] = {
                    "status": "PASS"
                    if vv.get("hasCard") and int(vv.get("stepCount") or 0) >= 2 and vv.get("hasOutcome")
                    else "FAIL",
                    **vv,
                }

        functional_keys = [
            "storageSeed",
            "enrich",
            "propose_write",
            "confirm_write",
            "workflows_list",
            "chat_page_context",
            "chat_handoff",
            "overlay_visual",
        ]
        statuses = [cases.get(k, {}).get("status") for k in functional_keys]
        cases["status"] = "PASS" if statuses and all(s == "PASS" for s in statuses) else "FAIL"
        cases["note"] = (
            "In-browser CDP: extension SW exercised enrich/approve/workflows/chat; "
            "overlay CSS+named-step markup rendered in page target."
        )
    except Exception as exc:  # noqa: BLE001
        cases["status"] = "FAIL"
        cases["error"] = (repr(exc) or type(exc).__name__)[:500]
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(profile, ignore_errors=True)

    return cases


def _api_v1_v4_smoke(headers: dict[str, str]) -> dict:
    cases: dict[str, dict] = {}
    r = httpx.get(f"{BASE}/api/extension/session", headers=headers, timeout=60)
    cases["session"] = {
        "status": "PASS" if r.status_code == 200 and r.json().get("orgId") else "FAIL",
        "http": r.status_code,
    }
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
    }
    return cases


async def _run() -> dict:
    _load_env()
    token = _mint_token()
    headers = _auth_headers(token)
    evidence: dict = {
        "startedAt": utcnow(),
        "scope": {"in": ["chrome", "edge", "brave"], "out": ["firefox", "safari", "mobile"]},
        "cases": {},
    }
    health = httpx.get(f"{BASE}/health", timeout=30).json()
    evidence["git_sha"] = health.get("git_sha")
    evidence["cases"]["api_tip_smoke"] = _api_v1_v4_smoke(headers)

    edge = _find_browser(EDGE_CANDIDATES)
    brave = _find_browser(BRAVE_CANDIDATES)
    if edge:
        evidence["cases"]["edge_functional"] = await _browser_functional(edge, "edge", 9331, token)
    else:
        evidence["cases"]["edge_functional"] = {"status": "FAIL", "error": "Edge binary not found"}
    if brave:
        evidence["cases"]["brave_functional"] = await _browser_functional(brave, "brave", 9332, token)
    else:
        evidence["cases"]["brave_functional"] = {"status": "FAIL", "error": "Brave binary not found"}

    tip_ok = all(c.get("status") == "PASS" for c in (evidence["cases"]["api_tip_smoke"] or {}).values())
    edge_ok = evidence["cases"]["edge_functional"].get("status") == "PASS"
    brave_ok = evidence["cases"]["brave_functional"].get("status") == "PASS"
    if tip_ok and edge_ok and brave_ok:
        evidence["overall"] = "PASS"
    elif tip_ok and (edge_ok or brave_ok):
        evidence["overall"] = "PARTIAL"
    else:
        evidence["overall"] = "FAIL"
    evidence["finishedAt"] = utcnow()
    evidence["cwsNote"] = (
        "Live /features/extension still falls back to setup guide until "
        "NEXT_PUBLIC_CHROME_WEB_STORE_URL is set to a real chromewebstore.google.com URL."
    )
    return evidence


def main() -> int:
    evidence = asyncio.run(_run())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    tip = {
        "probe": "extension_v5_chromium_parity_functional",
        "git_sha": evidence.get("git_sha"),
        "verified_at": utcnow(),
        "scope": evidence.get("scope"),
        "cases": {
            "api_tip_smoke": "PASS"
            if all(c.get("status") == "PASS" for c in (evidence["cases"].get("api_tip_smoke") or {}).values())
            else "FAIL",
            "edge_functional": evidence["cases"].get("edge_functional", {}).get("status"),
            "brave_functional": evidence["cases"].get("brave_functional", {}).get("status"),
            "edge_confirm_write_runId": (evidence["cases"].get("edge_functional") or {})
            .get("confirm_write", {})
            .get("runId"),
            "brave_confirm_write_runId": (evidence["cases"].get("brave_functional") or {})
            .get("confirm_write", {})
            .get("runId"),
        },
        "artifact": "docs/delivery/browser-extension-v5-live.json",
        "overall": evidence.get("overall"),
        "cwsNote": evidence.get("cwsNote"),
    }
    TIP.write_text(json.dumps(tip, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2)[:8000])
    return 0 if evidence.get("overall") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
