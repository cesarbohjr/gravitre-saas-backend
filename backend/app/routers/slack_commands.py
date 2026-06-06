"""STA-108: Slack slash command interrupt channel."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from supabase import create_client

from app.config import Settings, get_settings
from app.services.agent_interrupt_service import request_interrupt, resolve_org_id_for_slack_team

router = APIRouter(prefix="/api/slack/commands", tags=["slack"])


def _verify_slack_signature(settings: Settings, timestamp: str, body: bytes, signature: str) -> bool:
    secret = (getattr(settings, "slack_signing_secret", None) or "").strip()
    if not secret:
        return True
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"v0={digest}", signature)


@router.post("/interrupt")
async def slack_interrupt_command(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not _verify_slack_signature(settings, timestamp, body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    form = parse_qs(body.decode("utf-8"))
    text = (form.get("text") or [""])[0].strip()
    team_id = (form.get("team_id") or [""])[0].strip()
    user_id = (form.get("user_id") or [""])[0].strip()

    parts = text.split()
    if len(parts) < 3 or parts[0].lower() != "interrupt":
        return {
            "response_type": "ephemeral",
            "text": "Usage: /gravitre interrupt <pause|cancel> <job|run> <id>",
        }

    signal = parts[1].lower()
    target_kind = parts[2].lower()
    target_id = parts[3] if len(parts) > 3 else ""
    if signal not in {"pause", "cancel"} or target_kind not in {"job", "run"} or not target_id:
        return {
            "response_type": "ephemeral",
            "text": "Usage: /gravitre interrupt <pause|cancel> <job|run> <id>",
        }

    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    org_id = resolve_org_id_for_slack_team(client, team_id)
    if not org_id:
        return {"response_type": "ephemeral", "text": "No Gravitre org linked to this Slack workspace."}

    target_type = "agent_job" if target_kind == "job" else "workflow_run"
    try:
        request_interrupt(
            client,
            org_id=org_id,
            target_type=target_type,  # type: ignore[arg-type]
            target_id=target_id,
            signal=signal,  # type: ignore[arg-type]
            actor_id=None,
            source="slack",
            metadata={"slackUserId": user_id, "teamId": team_id},
        )
    except ValueError as exc:
        return {"response_type": "ephemeral", "text": str(exc)}

    return {
        "response_type": "in_channel",
        "text": f"Gravitre: requested {signal} for {target_kind} `{target_id}`.",
    }
