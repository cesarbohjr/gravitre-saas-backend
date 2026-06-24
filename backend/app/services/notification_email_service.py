"""Transactional notification emails (platform SMTP with org connector fallback)."""
from __future__ import annotations

import html
import logging
import re
from typing import Any

from app.config import Settings
from app.connectors.email import send_email_smtp
from app.connectors.repository import get_connector_by_type, get_decrypted_secret
from app.public_urls import PRODUCTION_APP_URL, normalize_public_url

logger = logging.getLogger(__name__)

EMAIL_PREF_KEYS: dict[str, str] = {
    "run_completed": "email_run_completed",
    "run_failed": "email_run_failed",
}


def format_readable_text(raw: str | None, max_len: int = 600) -> str:
    if not raw or not str(raw).strip():
        return ""
    text = str(raw).strip()
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return f"{text[: max_len - 1]}…"
    return text


def extract_next_steps(
    subtasks: list[dict[str, Any]],
    final_recommendation: str | None,
) -> list[str]:
    steps: list[str] = []
    seen: set[str] = set()
    for row in subtasks:
        result = row.get("result")
        if not isinstance(result, dict):
            continue
        for key in ("recommended_actions", "recommendedActions"):
            actions = result.get(key)
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, str) and action.strip():
                        cleaned = format_readable_text(action, 200)
                        if cleaned and cleaned not in seen:
                            seen.add(cleaned)
                            steps.append(cleaned)
        single = result.get("recommendedAction") or result.get("recommended_action")
        if isinstance(single, str) and single.strip():
            cleaned = format_readable_text(single, 200)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                steps.append(cleaned)
    if final_recommendation:
        cleaned = format_readable_text(final_recommendation, 200)
        if cleaned and cleaned not in seen:
            steps.append(cleaned)
    return steps[:5]


def resolve_user_email(client: Any, org_id: str, user_id: str) -> str | None:
    if not user_id:
        return None
    try:
        response = (
            client.table("users")
            .select("email")
            .eq("id", user_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        if response.data:
            email = str(response.data[0].get("email") or "").strip()
            if email:
                return email
    except Exception as exc:  # noqa: BLE001
        logger.warning("resolve_user_email failed user_id=%s: %s", user_id, exc)
    return None


def email_notifications_enabled(
    client: Any,
    org_id: str,
    user_id: str,
    notification_type: str,
) -> bool:
    pref_key = EMAIL_PREF_KEYS.get(notification_type, f"email_{notification_type}")
    try:
        response = (
            client.table("notification_preferences")
            .select("preferences")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return True
        preferences = response.data[0].get("preferences") or {}
        if not isinstance(preferences, dict):
            return True
        if pref_key not in preferences:
            return True
        return bool(preferences.get(pref_key))
    except Exception as exc:  # noqa: BLE001
        logger.warning("email preference lookup failed user_id=%s: %s", user_id, exc)
        return True


def _app_base_url(settings: Settings) -> str:
    base = normalize_public_url(settings.public_app_url, fallback=PRODUCTION_APP_URL)
    return base.rstrip("/")


def _platform_smtp_configured(settings: Settings) -> bool:
    return bool(
        settings.notification_email_enabled
        and (settings.notification_smtp_host or "").strip()
        and (settings.notification_smtp_from or "").strip()
    )


def _send_email(
    settings: Settings,
    *,
    to_addr: str,
    subject: str,
    html_body: str,
    client: Any | None = None,
    org_id: str | None = None,
) -> bool:
    if _platform_smtp_configured(settings):
        try:
            send_email_smtp(
                host=settings.notification_smtp_host.strip(),
                port=int(settings.notification_smtp_port or 587),
                username=(settings.notification_smtp_username or "").strip(),
                password=(settings.notification_smtp_password or "").strip(),
                from_addr=settings.notification_smtp_from.strip(),
                to_addr=to_addr,
                subject=subject,
                body=html_body,
                content_type="text/html",
                use_tls=settings.notification_smtp_use_tls,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("platform notification email failed to=%s: %s", to_addr, exc)

    if client and org_id:
        return _send_via_org_email_connector(
            client,
            settings,
            org_id=org_id,
            to_addr=to_addr,
            subject=subject,
            html_body=html_body,
        )
    return False


def _send_via_org_email_connector(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    to_addr: str,
    subject: str,
    html_body: str,
) -> bool:
    if settings.disable_connectors:
        return False
    conn = get_connector_by_type(client, org_id, "email")
    if not conn:
        logger.info("swarm completion email skipped: no org email connector org_id=%s", org_id)
        return False
    connector_id = str(conn["id"])
    conn_config = conn.get("config") or {}
    use_tls = conn_config.get("use_tls", True)
    smtp_host = get_decrypted_secret(client, connector_id, "SMTP_HOST", settings)
    smtp_port = get_decrypted_secret(client, connector_id, "SMTP_PORT", settings)
    smtp_user = get_decrypted_secret(client, connector_id, "SMTP_USERNAME", settings)
    smtp_pass = get_decrypted_secret(client, connector_id, "SMTP_PASSWORD", settings)
    smtp_from = get_decrypted_secret(client, connector_id, "SMTP_FROM", settings)
    if not smtp_host or not smtp_from:
        logger.info("swarm completion email skipped: email connector incomplete org_id=%s", org_id)
        return False
    port = int(smtp_port) if smtp_port else (587 if use_tls else 25)
    try:
        send_email_smtp(
            host=smtp_host,
            port=port,
            username=smtp_user or "",
            password=smtp_pass or "",
            from_addr=smtp_from,
            to_addr=to_addr,
            subject=subject,
            body=html_body,
            content_type="text/html",
            use_tls=use_tls,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("org email connector send failed org_id=%s: %s", org_id, exc)
        return False


def build_swarm_completion_email(
    settings: Settings,
    *,
    swarm_run_id: str,
    objective: str,
    final_recommendation: str | None,
    final_confidence: float | None,
    decision_method: str,
    next_steps: list[str],
    dissenting_opinions: list[str] | None = None,
) -> tuple[str, str]:
    summary = format_readable_text(final_recommendation, 900) or "Your agent swarm finished successfully."
    decision_label = decision_method.replace("_", " ").title()
    confidence_line = (
        f"Council confidence: {int(final_confidence * 100)}%"
        if final_confidence is not None
        else ""
    )
    view_url = f"{_app_base_url(settings)}/agents/swarm?runId={swarm_run_id}"
    subject = f"Agent swarm complete: {objective[:70]}"

    steps_html = ""
    if next_steps:
        items = "".join(f"<li style='margin-bottom:8px;'>{html.escape(step)}</li>" for step in next_steps)
        steps_html = f"""
        <h2 style="font-size:16px;margin:24px 0 8px;color:#111827;">Suggested next steps</h2>
        <ol style="margin:0;padding-left:20px;color:#374151;line-height:1.5;">{items}</ol>
        """

    dissent_html = ""
    if dissenting_opinions:
        items = "".join(
            f"<li style='margin-bottom:6px;'>{html.escape(format_readable_text(item, 180))}</li>"
            for item in dissenting_opinions[:3]
            if item
        )
        if items:
            dissent_html = f"""
            <h2 style="font-size:14px;margin:24px 0 8px;color:#92400e;">Alternate views</h2>
            <ul style="margin:0;padding-left:20px;color:#78350f;line-height:1.5;">{items}</ul>
            """

    meta_bits = [bit for bit in [decision_label, confidence_line] if bit]
    meta_html = " · ".join(html.escape(bit) for bit in meta_bits)

    html_body = f"""<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e5e7eb;">
            <tr>
              <td style="padding:24px 24px 12px;background:linear-gradient(135deg,#059669,#2563eb);color:#ffffff;">
                <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.9;">Gravitre Agent Swarm</div>
                <h1 style="margin:8px 0 0;font-size:22px;line-height:1.3;">Swarm complete</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:24px;color:#111827;">
                <p style="margin:0 0 12px;font-size:14px;color:#6b7280;">Objective</p>
                <p style="margin:0 0 20px;font-size:16px;line-height:1.5;font-weight:600;">{html.escape(objective)}</p>
                <div style="border-radius:12px;background:#ecfdf5;border:1px solid #a7f3d0;padding:16px;margin-bottom:8px;">
                  <p style="margin:0 0 8px;font-size:12px;font-weight:700;color:#047857;text-transform:uppercase;letter-spacing:0.06em;">Council recommendation</p>
                  <p style="margin:0;font-size:15px;line-height:1.6;color:#064e3b;">{html.escape(summary)}</p>
                </div>
                <p style="margin:12px 0 0;font-size:13px;color:#6b7280;">{meta_html}</p>
                {steps_html}
                {dissent_html}
                <div style="margin-top:28px;text-align:center;">
                  <a href="{html.escape(view_url)}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:999px;font-size:14px;font-weight:600;">
                    View full results
                  </a>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    return subject, html_body


def send_swarm_completion_email(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    swarm_run_id: str,
    objective: str,
    final_recommendation: str | None,
    final_confidence: float | None,
    decision_method: str,
    subtasks: list[dict[str, Any]],
    dissenting_opinions: list[str] | None = None,
) -> bool:
    if not settings.notification_email_enabled:
        return False
    if not email_notifications_enabled(client, org_id, user_id, "run_completed"):
        return False
    to_addr = resolve_user_email(client, org_id, user_id)
    if not to_addr:
        logger.info("swarm completion email skipped: no user email user_id=%s", user_id)
        return False

    next_steps = extract_next_steps(subtasks, final_recommendation)
    subject, html_body = build_swarm_completion_email(
        settings,
        swarm_run_id=swarm_run_id,
        objective=objective,
        final_recommendation=final_recommendation,
        final_confidence=final_confidence,
        decision_method=decision_method,
        next_steps=next_steps,
        dissenting_opinions=dissenting_opinions,
    )
    sent = _send_email(
        settings,
        to_addr=to_addr,
        subject=subject,
        html_body=html_body,
        client=client,
        org_id=org_id,
    )
    if sent:
        logger.info("swarm completion email sent swarm_run_id=%s user_id=%s", swarm_run_id, user_id)
    return sent
