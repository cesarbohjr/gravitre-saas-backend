"""Slack Web API client (OAuth bot token)."""
from __future__ import annotations

import hashlib
import time
from typing import Any

import httpx

SLACK_API_BASE = "https://slack.com/api"
TIMEOUT_SEC = 15
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


def slack_api_call(
    token: str,
    method: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call a Slack Web API method; raises ValueError on API errors."""
    if not (token or "").strip():
        raise ValueError("Slack token is required")
    url = f"{SLACK_API_BASE}/{method}"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            start = time.perf_counter()
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                if json_body is not None:
                    response = client.post(url, headers=headers, json=json_body)
                else:
                    response = client.get(url, headers=headers, params=params or {})
            data = response.json() if response.text else {}
            if not response.is_success:
                if response.status_code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                    continue
                err = data.get("error", f"http_{response.status_code}")
                raise ValueError(f"Slack API error: {err}")
            if not data.get("ok"):
                raise ValueError(data.get("error", "Slack API returned ok=false"))
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            data["_latency_ms"] = elapsed_ms
            return data
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ValueError("Slack API timeout") from exc
    if last_error:
        raise last_error
    raise ValueError("Slack API call failed")


def send_slack_message(token: str, channel: str, text: str) -> dict[str, Any]:
    channel = (channel or "").strip()
    if not channel:
        raise ValueError("Slack channel is required")
    if not (text or "").strip():
        raise ValueError("Slack message text is required")
    return slack_api_call(
        token,
        "chat.postMessage",
        json_body={"channel": channel, "text": text.strip()[:4000]},
    )


def list_conversations(
    token: str,
    *,
    types: str = "public_channel,private_channel",
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "types": types,
        "limit": min(max(int(limit), 1), 200),
        "exclude_archived": "true",
    }
    if cursor:
        params["cursor"] = cursor
    return slack_api_call(token, "conversations.list", params=params)


def conversation_history(
    token: str,
    channel: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    channel = (channel or "").strip()
    if not channel:
        raise ValueError("Slack channel is required")
    params: dict[str, Any] = {
        "channel": channel,
        "limit": min(max(int(limit), 1), 200),
    }
    if cursor:
        params["cursor"] = cursor
    return slack_api_call(token, "conversations.history", params=params)


def list_users(
    token: str,
    *,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": min(max(int(limit), 1), 200)}
    if cursor:
        params["cursor"] = cursor
    return slack_api_call(token, "users.list", params=params)


def get_user(token: str, user: str) -> dict[str, Any]:
    """Single user — users.info."""
    user = (user or "").strip()
    if not user:
        raise ValueError("Slack user id is required")
    return slack_api_call(token, "users.info", params={"user": user})


def join_conversation(token: str, channel: str) -> dict[str, Any]:
    """Join a public channel — conversations.join (channels:join)."""
    channel = (channel or "").strip()
    if not channel:
        raise ValueError("Slack channel is required")
    return slack_api_call(token, "conversations.join", json_body={"channel": channel})


def create_conversation(
    token: str,
    name: str,
    *,
    is_private: bool = False,
) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("Slack channel name is required")
    return slack_api_call(
        token,
        "conversations.create",
        json_body={"name": name, "is_private": bool(is_private)},
    )


def update_message(
    token: str,
    channel: str,
    ts: str,
    text: str,
) -> dict[str, Any]:
    channel = (channel or "").strip()
    if not channel or not (ts or "").strip():
        raise ValueError("Slack channel and ts are required")
    if not (text or "").strip():
        raise ValueError("Slack message text is required")
    return slack_api_call(
        token,
        "chat.update",
        json_body={"channel": channel, "ts": str(ts).strip(), "text": text.strip()[:4000]},
    )


def upload_file(
    token: str,
    *,
    channels: str | list[str] | None = None,
    content: str | None = None,
    filename: str | None = None,
    initial_comment: str | None = None,
) -> dict[str, Any]:
    if not content and not filename:
        raise ValueError("Slack files.upload requires content or filename")
    data: dict[str, Any] = {}
    if channels:
        if isinstance(channels, list):
            data["channels"] = ",".join(str(c) for c in channels)
        else:
            data["channels"] = str(channels)
    if content is not None:
        data["content"] = str(content)
    if filename:
        data["filename"] = str(filename)
    if initial_comment:
        data["initial_comment"] = str(initial_comment)[:1000]
    url = f"{SLACK_API_BASE}/files.upload"
    headers = {"Authorization": f"Bearer {token.strip()}"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(url, headers=headers, data=data)
    payload = response.json() if response.text else {}
    if not response.is_success or not payload.get("ok"):
        raise ValueError(payload.get("error", f"http_{response.status_code}"))
    return payload


def add_reaction(
    token: str,
    channel: str,
    timestamp: str,
    name: str,
) -> dict[str, Any]:
    if not channel or not timestamp or not (name or "").strip():
        raise ValueError("Slack reactions.add requires channel, timestamp, and name")
    return slack_api_call(
        token,
        "reactions.add",
        json_body={"channel": channel, "timestamp": str(timestamp), "name": name.strip()},
    )


def trigger_workflow(
    token: str,
    *,
    trigger_id: str | None = None,
    workflow: str | None = None,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if trigger_id:
        body["trigger_id"] = str(trigger_id)
    if workflow:
        body["workflow"] = str(workflow)
    if inputs:
        body["inputs"] = inputs
    if not body:
        raise ValueError("Slack workflows.trigger requires trigger_id or workflow")
    return slack_api_call(token, "workflows.triggers", json_body=body)


def message_hash(text: str) -> str:
    """Hash for audit (no PII, no message text)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
