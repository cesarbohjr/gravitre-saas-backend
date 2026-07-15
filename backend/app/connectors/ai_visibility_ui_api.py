"""Allowlisted consumer-UI AI visibility capture (S2).

Surfaces: ChatGPT, Perplexity, Gemini, Copilot, Claude only.
LinkedIn and cookie theft / proxy farms are explicitly out of scope.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any, Coroutine, TypeVar

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.browser_agent_service import (
    BrowserAgentError,
    browser_agent_interact,
    browser_agent_read,
)

T = TypeVar("T")

ALLOWED_SURFACES: dict[str, dict[str, str]] = {
    "chatgpt": {
        "id": "chatgpt",
        "label": "ChatGPT",
        "entry_url": "https://chatgpt.com",
    },
    "perplexity": {
        "id": "perplexity",
        "label": "Perplexity",
        "entry_url": "https://www.perplexity.ai",
    },
    "gemini": {
        "id": "gemini",
        "label": "Gemini",
        "entry_url": "https://gemini.google.com",
    },
    "copilot": {
        "id": "copilot",
        "label": "Copilot",
        "entry_url": "https://copilot.microsoft.com",
    },
    "claude": {
        "id": "claude",
        "label": "Claude",
        "entry_url": "https://claude.ai",
    },
}

_PREVIEW_MAX = 500
_BATCH_MAX_CHECKS = 20

# Minimal fill/submit selectors — best-effort; SPAs vary and may fail without interact.
_SURFACE_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "chatgpt": [
        {"type": "fill", "selector": "textarea, [contenteditable='true']", "value": "{prompt}"},
        {"type": "click", "selector": "button[data-testid='send-button'], button[aria-label*='Send']"},
        {"type": "wait", "ms": 4000},
    ],
    "perplexity": [
        {"type": "fill", "selector": "textarea, [contenteditable='true']", "value": "{prompt}"},
        {"type": "click", "selector": "button[aria-label*='Submit'], button[type='submit']"},
        {"type": "wait", "ms": 4000},
    ],
    "gemini": [
        {"type": "fill", "selector": "textarea, [contenteditable='true']", "value": "{prompt}"},
        {"type": "click", "selector": "button[aria-label*='Send'], button[type='submit']"},
        {"type": "wait", "ms": 4000},
    ],
    "copilot": [
        {"type": "fill", "selector": "textarea, [contenteditable='true']", "value": "{prompt}"},
        {"type": "click", "selector": "button[aria-label*='Submit'], button[type='submit']"},
        {"type": "wait", "ms": 4000},
    ],
    "claude": [
        {"type": "fill", "selector": "textarea, [contenteditable='true']", "value": "{prompt}"},
        {"type": "click", "selector": "button[aria-label*='Send'], button[type='submit']"},
        {"type": "wait", "ms": 4000},
    ],
}


class AiVisibilityUiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def resolve_ai_visibility_ui_connector(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str | None]:
    """Resolve connector. API key is optional (runner uses browser_agent flags)."""
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(
            client, org_id, "ai_visibility_ui", environment_name=environment_name
        )
    if not conn:
        raise AiVisibilityUiError("No active AI Visibility UI connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    # Accept connector present even without a key — capture is runner-gated.
    return cid, (api_key.strip() if api_key else None)


def surfaces_list() -> list[dict[str, str]]:
    return [
        {"id": s["id"], "label": s["label"], "entry_url": s["entry_url"]}
        for s in ALLOWED_SURFACES.values()
    ]


def _reject_linkedin(surface: str, entry_url: str | None = None) -> None:
    blob = f"{surface or ''} {entry_url or ''}".lower()
    if "linkedin" in blob or "linkedin.com" in blob:
        raise AiVisibilityUiError(
            "LinkedIn surfaces are forbidden for AI Visibility UI capture",
            status_code=403,
            details={"surface": surface, "entry_url": entry_url},
        )


def _normalize_surface(surface: str) -> dict[str, str]:
    key = str(surface or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "chat_gpt": "chatgpt",
        "openai": "chatgpt",
        "google_gemini": "gemini",
        "microsoft_copilot": "copilot",
        "bing_copilot": "copilot",
        "anthropic": "claude",
    }
    key = aliases.get(key, key)
    _reject_linkedin(key)
    if key not in ALLOWED_SURFACES:
        raise AiVisibilityUiError(
            f"Surface '{surface}' is not allowlisted. Allowed: {', '.join(ALLOWED_SURFACES)}",
            status_code=400,
        )
    meta = ALLOWED_SURFACES[key]
    _reject_linkedin(meta["id"], meta["entry_url"])
    return meta


def _truncate_preview(text: str | None) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    if len(raw) <= _PREVIEW_MAX:
        return raw
    return raw[: _PREVIEW_MAX - 3] + "..."


def _brand_mentioned(brand: str, text: str | None) -> bool | None:
    brand_norm = str(brand or "").strip()
    body = str(text or "")
    if not brand_norm or not body:
        return None
    return brand_norm.lower() in body.lower()


def _interact_actions(surface_id: str, prompt: str) -> list[dict[str, Any]]:
    template = _SURFACE_ACTIONS.get(surface_id) or _SURFACE_ACTIONS["chatgpt"]
    out: list[dict[str, Any]] = []
    for step in template:
        cloned = dict(step)
        if "value" in cloned and isinstance(cloned["value"], str):
            cloned["value"] = cloned["value"].replace("{prompt}", prompt)
        out.append(cloned)
    return out


def mentions_check(
    *,
    brand: str,
    prompt: str,
    surface: str,
    settings: Settings,
    client: Any = None,
    org_id: str | None = None,
    connector_id: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Check whether brand appears in a consumer-UI AI answer (allowlisted surfaces only)."""
    _ = (client, org_id, connector_id)  # reserved for future runner session binding
    brand_name = str(brand or "").strip()
    prompt_text = str(prompt or "").strip()
    if not brand_name:
        raise AiVisibilityUiError("brand is required", status_code=400)
    if not prompt_text:
        raise AiVisibilityUiError("prompt is required", status_code=400)

    meta = _normalize_surface(surface)
    entry_url = meta["entry_url"]
    surface_id = meta["id"]
    interact_enabled = bool(getattr(settings, "browser_agent_interact_enabled", False))

    capture_text: str | None = None
    capture_mode: str | None = None
    error: str | None = None
    ok = False
    mentioned: bool | None = None

    if interact_enabled:
        try:
            result = _run_async(
                browser_agent_interact(
                    entry_url,
                    actions=_interact_actions(surface_id, prompt_text),
                    settings=settings,
                    approval_id=approval_id,
                )
            )
            if isinstance(result, dict) and result.get("pending_approval"):
                error = (
                    "browser_agent_interact requires approval_id before UI automation. "
                    "Pass approval_id or enable a governed approval path."
                )
                capture_mode = "pending_approval"
            elif isinstance(result, dict):
                capture_text = str(result.get("text") or "")
                capture_mode = str(result.get("mode") or "playwright_interact")
                mentioned = _brand_mentioned(brand_name, capture_text)
                ok = True
        except BrowserAgentError as exc:
            error = str(exc)
            capture_mode = "interact_failed"
        except Exception as exc:  # noqa: BLE001
            error = f"Interact capture failed: {exc}"
            capture_mode = "interact_failed"

    if not ok:
        # Read-only fallback when interact disabled or failed — landing page only (no LinkedIn).
        try:
            read_result = _run_async(browser_agent_read(entry_url, settings=settings))
            if isinstance(read_result, dict):
                capture_text = str(read_result.get("text") or "")
                if not capture_mode:
                    capture_mode = str(read_result.get("mode") or "httpx_read")
        except BrowserAgentError as exc:
            if not error:
                error = str(exc)
        except Exception as exc:  # noqa: BLE001
            if not error:
                error = f"Read capture failed: {exc}"

        if not interact_enabled:
            error = (
                error
                or "Browser interact runner is disabled. Set BROWSER_AGENT_INTERACT_ENABLED=true "
                "for reliable consumer-UI mention capture."
            )
            mentioned = None
            ok = False
        elif mentioned is None and capture_text:
            # Interact failed but read returned text — still not a prompt answer.
            mentioned = None
            ok = False
            if not error:
                error = "Interact capture unavailable; read-only landing page is not a mention check"

    preview = _truncate_preview(capture_text)
    return {
        "ok": ok,
        "brand": brand_name,
        "prompt": prompt_text,
        "surface": surface_id,
        "mentioned": mentioned if ok else None,
        "capture_method": "ui_scrape",
        "capture_mode": capture_mode,
        "answer_preview": preview,
        "result_url": entry_url,
        "error": error,
        "connector_id": connector_id,
    }


def prompts_batch(
    *,
    brand: str,
    prompts: list[str],
    surfaces: list[str],
    settings: Settings,
    client: Any = None,
    org_id: str | None = None,
    connector_id: str | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    prompt_list = [str(p).strip() for p in (prompts or []) if str(p).strip()]
    surface_list = [str(s).strip() for s in (surfaces or []) if str(s).strip()]
    if not prompt_list:
        raise AiVisibilityUiError("prompts is required", status_code=400)
    if not surface_list:
        raise AiVisibilityUiError("surfaces is required", status_code=400)

    # Pre-validate (hard-reject LinkedIn / unknown surfaces before any network I/O).
    for s in surface_list:
        _normalize_surface(s)

    planned = len(prompt_list) * len(surface_list)
    if planned > _BATCH_MAX_CHECKS:
        raise AiVisibilityUiError(
            f"Batch exceeds max {_BATCH_MAX_CHECKS} checks ({planned} planned)",
            status_code=400,
        )

    results: list[dict[str, Any]] = []
    for prompt in prompt_list:
        for surface in surface_list:
            results.append(
                mentions_check(
                    brand=brand,
                    prompt=prompt,
                    surface=surface,
                    settings=settings,
                    client=client,
                    org_id=org_id,
                    connector_id=connector_id,
                    approval_id=approval_id,
                )
            )
    return {
        "brand": brand,
        "check_count": len(results),
        "max_checks": _BATCH_MAX_CHECKS,
        "results": results,
        "captures": results,
        "result_url": None,
        "capture_method": "ui_scrape",
    }


def captures_export(*, captures: list[Any] | None = None) -> dict[str, Any]:
    """Normalize pass-through of last batch capture results."""
    rows_in = captures if isinstance(captures, list) else []
    normalized: list[dict[str, Any]] = []
    for item in rows_in:
        if not isinstance(item, dict):
            normalized.append({"raw": item, "capture_method": "ui_scrape"})
            continue
        surface = str(item.get("surface") or "")
        result_url = str(item.get("result_url") or "")
        try:
            _reject_linkedin(surface, result_url)
        except AiVisibilityUiError:
            continue
        preview = item.get("answer_preview") or item.get("preview") or item.get("text")
        normalized.append(
            {
                "brand": item.get("brand"),
                "prompt": item.get("prompt"),
                "surface": surface,
                "mentioned": item.get("mentioned"),
                "ok": item.get("ok"),
                "answer_preview": _truncate_preview(str(preview) if preview is not None else ""),
                "capture_method": item.get("capture_method") or "ui_scrape",
                "result_url": result_url or None,
                "error": item.get("error"),
            }
        )
    return {
        "row_count": len(normalized),
        "captures": normalized,
        "capture_method": "ui_scrape",
        "result_url": "https://gravitre.ai",
    }
