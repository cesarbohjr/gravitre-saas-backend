"""IN-10: Slack API client. Approval-gated; rate limit and retries."""
from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

SLACK_API_URL = "https://slack.com/api/chat.postMessage"
TIMEOUT_SEC = 15
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


def send_slack_message(
    token: str,
    channel: str,
    text: str,
) -> dict[str, Any]:
    """
    POST to Slack chat.postMessage. Returns API response.
    Raises on timeout or 5xx; raises ValueError on auth/invalid.
    """
    channel = (channel or "").strip()
    if not channel:
        raise ValueError("Slack channel is required")
    if not (text or "").strip():
        raise ValueError("Slack message text is required")
    if not (token or "").strip():
        raise ValueError("Slack token is required")

    payload: dict[str, Any] = {"channel": channel, "text": text.strip()[:4000]}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            start = time.perf_counter()
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                r = client.post(
                    SLACK_API_URL,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                )
            data = r.json() if r.text else {}
            if not r.is_success:
                if r.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                    continue
                err = data.get("error", f"http_{r.status_code}")
                raise ValueError(f"Slack API error: {err}")
            if not data.get("ok"):
                raise ValueError(data.get("error", "Slack API returned ok=false"))
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return {"_latency_ms": elapsed_ms, **(data or {})}
        except httpx.TimeoutException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ValueError("Slack API timeout") from e
    if last_error:
        raise last_error
    raise ValueError("Slack send failed")


def message_hash(text: str) -> str:
    """Hash for audit (no PII, no message text)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
