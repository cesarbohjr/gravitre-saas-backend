"""Org-wide approval rules from Settings > Human in the loop.

Four switches plus a decision SLA, stored on ``organizations.settings`` under
``approvalRules``. They sit on top of the per-subject ``hitl_policies`` rows
(see :mod:`app.services.hitl_policy_service`) and are applied where those are:

- ``customerEmailApproval``: email sends always wait for a person, even for an
  autonomous agent with an auto-run override (write_governance).
- ``twoApprovalsHighRisk``: delete-class actions and workflows that contain one
  need two approvals (HitlPolicyService.resolve and workflow execute).
- ``autoApproveReadOnly``: read-only lookups never wait, even when a policy
  lists ``read`` (HitlPolicyService.resolve).
- ``escalatePastDue``: requests past the decision SLA notify the org's admins
  and owners (ops_notifications_scheduler).
- ``sla``: how long a request may wait before it is past due.

Defaults keep today's behaviour, so an org that never opens the page is
unchanged: only the email rule is on, and it only tightens autonomous agents.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.logging import get_logger

logger = get_logger(__name__)

SETTINGS_KEY = "approvalRules"

# Decision SLA choices offered in the UI. "1bd" is one business day in the
# org's time zone (weekends skipped).
SLA_CHOICES: dict[str, int] = {"1h": 60, "4h": 240, "1bd": 24 * 60}
DEFAULT_SLA = "4h"

_EMAIL_CHANNEL = re.compile(r"\b(gmail|outlook|e-?mail|mail|smtp|sendgrid|mailgun|postmark|instantly|lemlist)\b", re.I)
_SEND_VERB = re.compile(r"\b(send|reply|forward)\b", re.I)
_HIGH_RISK_STEP = re.compile(
    r"\b(delete|remove|archive|destroy|drop|purge|revoke|refund|charge|payout|invoice|payment|bulk)\b",
    re.I,
)


@dataclass(frozen=True)
class ApprovalRules:
    customer_email_approval: bool = True
    two_approvals_high_risk: bool = False
    auto_approve_read_only: bool = False
    escalate_past_due: bool = False
    sla: str = DEFAULT_SLA

    @property
    def sla_minutes(self) -> int:
        return SLA_CHOICES.get(self.sla, SLA_CHOICES[DEFAULT_SLA])

    def to_api(self) -> dict[str, Any]:
        return {
            "customerEmailApproval": self.customer_email_approval,
            "twoApprovalsHighRisk": self.two_approvals_high_risk,
            "autoApproveReadOnly": self.auto_approve_read_only,
            "escalatePastDue": self.escalate_past_due,
            "sla": self.sla,
            "slaMinutes": self.sla_minutes,
        }


DEFAULT_RULES = ApprovalRules()

_API_TO_FIELD = {
    "customerEmailApproval": "customer_email_approval",
    "twoApprovalsHighRisk": "two_approvals_high_risk",
    "autoApproveReadOnly": "auto_approve_read_only",
    "escalatePastDue": "escalate_past_due",
}


def rules_from_settings(org_settings: dict[str, Any] | None) -> ApprovalRules:
    raw = (org_settings or {}).get(SETTINGS_KEY)
    if not isinstance(raw, dict):
        return DEFAULT_RULES
    values = asdict(DEFAULT_RULES)
    for api_key, field in _API_TO_FIELD.items():
        if isinstance(raw.get(api_key), bool):
            values[field] = raw[api_key]
    sla = str(raw.get("sla") or "")
    if sla in SLA_CHOICES:
        values["sla"] = sla
    return ApprovalRules(**values)


def merge_rules_update(current: ApprovalRules, update: dict[str, Any]) -> ApprovalRules:
    """Apply a partial API payload; unknown keys are ignored, bad values rejected."""
    values = asdict(current)
    for api_key, field in _API_TO_FIELD.items():
        if api_key in update:
            if not isinstance(update[api_key], bool):
                raise ValueError(f"{api_key} must be true or false")
            values[field] = update[api_key]
    if "sla" in update:
        sla = str(update["sla"] or "")
        if sla not in SLA_CHOICES:
            raise ValueError(f"sla must be one of {', '.join(SLA_CHOICES)}")
        values["sla"] = sla
    return ApprovalRules(**values)


def _load_org_settings(client: Any, org_id: str) -> dict[str, Any]:
    try:
        rows = (
            client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("approval_rules_load_failed org=%s error=%s", org_id, exc)
        return {}
    raw = rows[0].get("settings") if rows and isinstance(rows[0], dict) else None
    return raw if isinstance(raw, dict) else {}


def load_approval_rules(client: Any, org_id: str | None) -> ApprovalRules:
    if client is None or not str(org_id or "").strip():
        return DEFAULT_RULES
    return rules_from_settings(_load_org_settings(client, str(org_id)))


def load_rules_and_timezone(client: Any, org_id: str | None) -> tuple[ApprovalRules, str, bool]:
    """(rules, IANA time zone, whether the org picked its own decision SLA)."""
    if client is None or not str(org_id or "").strip():
        return DEFAULT_RULES, "UTC", False
    org_settings = _load_org_settings(client, str(org_id))
    raw = org_settings.get(SETTINGS_KEY)
    custom_sla = isinstance(raw, dict) and str(raw.get("sla") or "") in SLA_CHOICES
    return rules_from_settings(org_settings), timezone_from_settings(org_settings), custom_sla


def load_org_timezone(client: Any, org_id: str | None) -> str:
    if client is None or not str(org_id or "").strip():
        return "UTC"
    return timezone_from_settings(_load_org_settings(client, str(org_id)))


def timezone_from_settings(org_settings: dict[str, Any] | None) -> str:
    name = str((org_settings or {}).get("timezone") or "").strip()
    return name if is_valid_timezone(name) else "UTC"


def is_valid_timezone(name: str) -> bool:
    if not name:
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def is_customer_email_action(invoke_action: str | None, label: str | None = None) -> bool:
    """True for actions that send an email to someone (gmail.send_message, email.send...)."""
    blob = re.sub(r"[._/-]+", " ", f"{invoke_action or ''} {label or ''}")
    return bool(_EMAIL_CHANNEL.search(blob) and _SEND_VERB.search(blob))


def definition_has_high_risk_step(definition: dict[str, Any] | None) -> bool:
    """True when a workflow definition contains a delete, money or bulk step."""
    if not isinstance(definition, dict):
        return False
    for step in definition.get("steps") or []:
        if not isinstance(step, dict):
            continue
        config = step.get("config") if isinstance(step.get("config"), dict) else {}
        parts = [
            step.get("name"),
            step.get("type"),
            step.get("action"),
            step.get("invoke_action"),
            config.get("action"),
            config.get("invoke_action"),
            config.get("operation"),
        ]
        if _HIGH_RISK_STEP.search(" ".join(str(p or "").replace("_", " ").replace(".", " ") for p in parts)):
            return True
    return False


def sla_deadline(started: datetime, rules: ApprovalRules, tz_name: str = "UTC") -> datetime:
    """When a request that started at ``started`` becomes past due."""
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if rules.sla != "1bd":
        return started + timedelta(minutes=rules.sla_minutes)
    try:
        tz = ZoneInfo(tz_name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    local = started.astimezone(tz)
    nxt = local + timedelta(days=1)
    while nxt.weekday() >= 5:  # Saturday, Sunday
        nxt += timedelta(days=1)
    return nxt.astimezone(timezone.utc)


def required_approvals_for_definition(
    client: Any,
    org_id: str | None,
    definition: dict[str, Any] | None,
    required: int,
) -> int:
    """Raise a run that already needs approval to two when it holds a high-risk step."""
    if required < 1 or required >= 2 or not definition_has_high_risk_step(definition):
        return required
    if not load_approval_rules(client, org_id).two_approvals_high_risk:
        return required
    return 2
