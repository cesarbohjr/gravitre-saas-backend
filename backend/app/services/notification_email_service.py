"""Transactional notification emails (platform SMTP with org connector fallback)."""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.connectors.email import send_email_smtp
from app.connectors.repository import get_connector_by_type, get_decrypted_secret
from app.public_urls import PRODUCTION_APP_URL, normalize_public_url
from app.services.branding_service import get_org_branding

logger = logging.getLogger(__name__)

EMAIL_PREF_KEYS: dict[str, str] = {
    "run_completed": "email_run_completed",
    "run_failed": "email_run_failed",
    "assignment_completed": "email_assignment_completed",
    "trial_ending": "email_trial_ending",
    "payment_failed": "email_payment_failed",
}

GRAVITRE_PRIMARY = "#0091FF"
GRAVITRE_ACCENT = "#7C3AED"
GRAVITRE_SLATE = "#0F172A"
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class EmailBrandContext:
    brand_name: str
    logo_url: str
    primary_color: str
    accent_color: str
    hide_powered_by: bool
    app_base_url: str


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


def _normalize_hex(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not _HEX_RE.match(raw):
        return fallback.upper()
    if len(raw) == 4:
        return f"#{raw[1]}{raw[1]}{raw[2]}{raw[2]}{raw[3]}{raw[3]}".upper()
    return raw.upper()


def _absolute_asset_url(base_url: str, value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw
    if raw.startswith("//"):
        return f"https:{raw}"
    if raw.startswith("/"):
        return f"{base_url}{raw}"
    return f"{base_url}/{raw.lstrip('/')}"


def _platform_email_brand(settings: Settings, app_base_url: str) -> EmailBrandContext:
    brand_name = (settings.notification_email_brand_name or "Gravitre").strip() or "Gravitre"
    logo_override = (settings.notification_email_logo_url or "").strip()
    logo_url = _absolute_asset_url(app_base_url, logo_override) or f"{app_base_url}/logo-white.svg"
    primary = _normalize_hex(settings.notification_email_primary_color or GRAVITRE_PRIMARY, GRAVITRE_PRIMARY)
    accent = _normalize_hex(settings.notification_email_accent_color or GRAVITRE_ACCENT, GRAVITRE_ACCENT)
    return EmailBrandContext(
        brand_name=brand_name,
        logo_url=logo_url,
        primary_color=primary,
        accent_color=accent,
        hide_powered_by=False,
        app_base_url=app_base_url,
    )


def load_org_email_branding(client: Any, org_id: str, settings: Settings) -> EmailBrandContext:
    """Resolve org white-label branding with Gravitre platform defaults as fallback."""
    defaults = _platform_email_brand(settings, _app_base_url(settings))
    org_settings: dict[str, Any] | None = None
    try:
        response = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
        if response.data:
            raw = response.data[0].get("settings")
            org_settings = raw if isinstance(raw, dict) else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("load_org_email_branding failed org_id=%s: %s", org_id, exc)

    branding = get_org_branding(org_settings)
    brand_name = str(branding.get("emailFromName") or defaults.brand_name).strip() or defaults.brand_name
    logo_url = _absolute_asset_url(defaults.app_base_url, branding.get("logoUrl")) or defaults.logo_url

    org_primary = branding.get("primaryColor")
    if org_primary and str(org_primary).strip() and str(org_primary).upper() != GRAVITRE_SLATE:
        primary_color = _normalize_hex(org_primary, defaults.primary_color)
    else:
        primary_color = defaults.primary_color

    accent_color = defaults.accent_color
    hide_powered_by = bool(branding.get("hidePoweredBy"))

    return EmailBrandContext(
        brand_name=brand_name,
        logo_url=logo_url,
        primary_color=primary_color,
        accent_color=accent_color,
        hide_powered_by=hide_powered_by,
        app_base_url=defaults.app_base_url,
    )


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


def _topology_nodes_html(primary: str, accent: str) -> str:
    """Email-safe hub topology accent (Integration Hub metaphor)."""
    return f"""
    <table role="presentation" cellspacing="0" cellpadding="0" style="margin:18px auto 0;">
      <tr>
        <td align="center" style="padding:0 6px;">
          <div style="width:10px;height:10px;border-radius:999px;background:{primary};opacity:0.95;"></div>
        </td>
        <td style="width:28px;height:2px;background:linear-gradient(90deg,{primary},{accent});font-size:0;line-height:0;">&nbsp;</td>
        <td align="center" style="padding:0 6px;">
          <div style="width:14px;height:14px;border-radius:999px;background:#ffffff;box-shadow:0 0 0 3px rgba(255,255,255,0.35);"></div>
        </td>
        <td style="width:28px;height:2px;background:linear-gradient(90deg,{accent},{primary});font-size:0;line-height:0;">&nbsp;</td>
        <td align="center" style="padding:0 6px;">
          <div style="width:10px;height:10px;border-radius:999px;background:{accent};opacity:0.95;"></div>
        </td>
      </tr>
    </table>
    """


def build_swarm_completion_email(
    brand: EmailBrandContext,
    *,
    swarm_run_id: str,
    objective: str,
    final_recommendation: str | None,
    final_confidence: float | None,
    decision_method: str,
    next_steps: list[str],
    dissenting_opinions: list[str] | None = None,
) -> tuple[str, str]:
    summary = format_readable_text(final_recommendation, 900) or "Your multi-agent run finished successfully."
    decision_label = decision_method.replace("_", " ").title()
    confidence_pct = int(final_confidence * 100) if final_confidence is not None else None
    view_url = f"{brand.app_base_url}/agents/swarm?runId={swarm_run_id}"
    subject = f"{brand.brand_name} · Swarm complete — {objective[:64]}"
    preheader = format_readable_text(summary, 120) or f"Council recommendation ready for: {objective[:80]}"

    steps_html = ""
    if next_steps:
        items = "".join(
            f"""
            <tr>
              <td valign="top" style="width:28px;padding:0 10px 12px 0;">
                <div style="width:24px;height:24px;border-radius:999px;background:{brand.primary_color};color:#ffffff;font-size:12px;font-weight:700;line-height:24px;text-align:center;">
                  {index}
                </div>
              </td>
              <td valign="top" style="padding:0 0 12px;color:#334155;font-size:14px;line-height:1.55;">
                {html.escape(step)}
              </td>
            </tr>
            """
            for index, step in enumerate(next_steps, start=1)
        )
        steps_html = f"""
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:24px;">
          <tr>
            <td style="padding-bottom:10px;font-size:12px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">
              Suggested next steps
            </td>
          </tr>
          {items}
        </table>
        """

    dissent_html = ""
    if dissenting_opinions:
        items = "".join(
            f"<li style='margin:0 0 8px;color:#92400e;font-size:13px;line-height:1.5;'>{html.escape(format_readable_text(item, 180))}</li>"
            for item in dissenting_opinions[:3]
            if item
        )
        if items:
            dissent_html = f"""
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:18px;">
              <tr>
                <td style="border-radius:12px;border:1px dashed #fcd34d;background:#fffbeb;padding:14px 16px;">
                  <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#b45309;margin-bottom:8px;">
                    Alternate views
                  </div>
                  <ul style="margin:0;padding-left:18px;">{items}</ul>
                </td>
              </tr>
            </table>
            """

    confidence_chip = ""
    if confidence_pct is not None:
        confidence_chip = f"""
        <td style="padding-right:8px;padding-bottom:8px;">
          <span style="display:inline-block;padding:6px 10px;border-radius:999px;background:#eff6ff;color:{brand.primary_color};font-size:12px;font-weight:600;border:1px solid #dbeafe;">
            {confidence_pct}% confidence
          </span>
        </td>
        """

    footer_powered = ""
    if not brand.hide_powered_by:
        footer_powered = f"""
        <tr>
          <td align="center" style="padding:16px 24px 24px;color:#94a3b8;font-size:11px;line-height:1.5;">
            Sent by {html.escape(brand.brand_name)} on Gravitre
          </td>
        </tr>
        """

    html_body = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{html.escape(subject)}</title>
  </head>
  <body style="margin:0;padding:0;background:#eef2ff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">
      {html.escape(preheader)}
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:linear-gradient(180deg,#eef2ff 0%,#f8fafc 45%,#f1f5f9 100%);padding:32px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;">
            <tr>
              <td style="border-radius:20px 20px 0 0;padding:28px 28px 22px;background:linear-gradient(135deg,{brand.primary_color} 0%,{brand.accent_color} 100%);color:#ffffff;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td align="left" style="padding-bottom:8px;">
                      <img src="{html.escape(brand.logo_url)}" alt="{html.escape(brand.brand_name)} logo" width="120" style="display:block;max-width:120px;height:auto;border:0;" />
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;opacity:0.88;">
                        Multi-Agent Run · {html.escape(brand.brand_name)}
                      </div>
                      <h1 style="margin:8px 0 0;font-size:28px;line-height:1.15;font-weight:700;color:#ffffff;">
                        Council reached a decision
                      </h1>
                      <p style="margin:10px 0 0;font-size:14px;line-height:1.5;color:rgba(255,255,255,0.92);">
                        Your parallel agents finished and merged their work into one recommendation.
                      </p>
                    </td>
                  </tr>
                </table>
                {_topology_nodes_html(brand.primary_color, brand.accent_color)}
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;padding:28px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:18px;">
                  <tr>
                    <td style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;padding-bottom:6px;">
                      Objective
                    </td>
                  </tr>
                  <tr>
                    <td style="font-size:17px;line-height:1.45;font-weight:600;color:#0f172a;">
                      {html.escape(objective)}
                    </td>
                  </tr>
                </table>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:8px;">
                  <tr>
                    {confidence_chip}
                    <td style="padding-right:8px;padding-bottom:8px;">
                      <span style="display:inline-block;padding:6px 10px;border-radius:999px;background:#f8fafc;color:#475569;font-size:12px;font-weight:600;border:1px solid #e2e8f0;">
                        {html.escape(decision_label)}
                      </span>
                    </td>
                  </tr>
                </table>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="border-radius:16px;background:linear-gradient(180deg,#f8fafc 0%,#ffffff 100%);border:1px solid #dbeafe;padding:18px 18px 16px;box-shadow:0 10px 30px rgba(15,23,42,0.06);">
                      <div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:{brand.primary_color};margin-bottom:8px;">
                        Council recommendation
                      </div>
                      <div style="font-size:16px;line-height:1.65;color:#1e293b;">
                        {html.escape(summary)}
                      </div>
                    </td>
                  </tr>
                </table>

                {steps_html}
                {dissent_html}

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:28px;">
                  <tr>
                    <td align="center">
                      <a href="{html.escape(view_url)}" style="display:inline-block;background:{brand.primary_color};color:#ffffff;text-decoration:none;padding:14px 24px;border-radius:999px;font-size:14px;font-weight:700;box-shadow:0 8px 20px rgba(37,99,235,0.25);">
                        View full swarm results
                      </a>
                    </td>
                  </tr>
                  <tr>
                    <td align="center" style="padding-top:12px;">
                      <a href="{html.escape(view_url)}" style="color:#64748b;font-size:12px;text-decoration:underline;">
                        {html.escape(view_url)}
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff;border:1px solid #e2e8f0;border-top:0;border-radius:0 0 20px 20px;">
                {footer_powered}
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

    brand = load_org_email_branding(client, org_id, settings)
    next_steps = extract_next_steps(subtasks, final_recommendation)
    subject, html_body = build_swarm_completion_email(
        brand,
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
        logger.info(
            "swarm completion email sent swarm_run_id=%s user_id=%s brand=%s",
            swarm_run_id,
            user_id,
            brand.brand_name,
        )
    return sent


def _simple_completion_email(
    brand: EmailBrandContext,
    *,
    subject_prefix: str,
    headline: str,
    summary: str,
    view_url: str,
    cta_label: str,
) -> tuple[str, str]:
    subject = f"{brand.brand_name} · {subject_prefix}"
    html_body = f"""<!DOCTYPE html>
<html lang="en"><body style="margin:0;padding:24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;">
    <tr><td style="padding:24px;background:linear-gradient(135deg,{brand.primary_color},{brand.accent_color});color:#fff;border-radius:16px 16px 0 0;">
      <div style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.9;">{html.escape(brand.brand_name)}</div>
      <h1 style="margin:8px 0 0;font-size:22px;">{html.escape(headline)}</h1>
    </td></tr>
    <tr><td style="padding:24px;">
      <p style="margin:0 0 20px;font-size:15px;line-height:1.6;color:#334155;">{html.escape(summary)}</p>
      <a href="{html.escape(view_url)}" style="display:inline-block;background:{brand.primary_color};color:#fff;text-decoration:none;padding:12px 18px;border-radius:999px;font-weight:600;">{html.escape(cta_label)}</a>
    </td></tr>
  </table>
</body></html>"""
    return subject, html_body


def send_workflow_completion_email(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    run_id: str,
    workflow_name: str,
    final_status: str,
) -> bool:
    if not settings.notification_email_enabled:
        return False
    pref_type = "run_completed" if final_status == "completed" else "run_failed"
    if not email_notifications_enabled(client, org_id, user_id, pref_type):
        return False
    to_addr = resolve_user_email(client, org_id, user_id)
    if not to_addr:
        return False
    brand = load_org_email_branding(client, org_id, settings)
    view_url = f"{brand.app_base_url}/runs/{run_id}"
    if final_status == "completed":
        summary = f"Workflow “{workflow_name}” finished successfully."
        headline = "Workflow completed"
        prefix = "Workflow complete"
    else:
        summary = f"Workflow “{workflow_name}” failed. Review the run for step-level errors."
        headline = "Workflow failed"
        prefix = "Workflow failed"
    subject, html_body = _simple_completion_email(
        brand,
        subject_prefix=prefix,
        headline=headline,
        summary=summary,
        view_url=view_url,
        cta_label="View run details",
    )
    return _send_email(
        settings,
        to_addr=to_addr,
        subject=subject,
        html_body=html_body,
        client=client,
        org_id=org_id,
    )


def send_assignment_completion_email(
    client: Any,
    settings: Settings,
    *,
    org_id: str,
    user_id: str,
    job_id: str,
    task_title: str,
    requires_approval: bool,
) -> bool:
    if not settings.notification_email_enabled:
        return False
    if not email_notifications_enabled(client, org_id, user_id, "assignment_completed"):
        return False
    to_addr = resolve_user_email(client, org_id, user_id)
    if not to_addr:
        return False
    brand = load_org_email_branding(client, org_id, settings)
    view_url = f"{brand.app_base_url}/assignments/{job_id}"
    if requires_approval:
        summary = f"Assignment “{task_title}” is ready for your review and approval."
        headline = "Assignment needs approval"
    else:
        summary = f"Assignment “{task_title}” completed successfully."
        headline = "Assignment completed"
    subject, html_body = _simple_completion_email(
        brand,
        subject_prefix="Assignment update",
        headline=headline,
        summary=summary,
        view_url=view_url,
        cta_label="Open assignment",
    )
    return _send_email(
        settings,
        to_addr=to_addr,
        subject=subject,
        html_body=html_body,
        client=client,
        org_id=org_id,
    )
