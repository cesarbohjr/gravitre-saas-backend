"""Per-agent PSTN voice policy — reuses Agent Identity IAM, not uniform defaults."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.services.agent_identity_service import (
    EffectiveAgentIdentity,
    enforce_agent_identity_before_tool,
    resolve_effective_identity,
)

VoicePolicyScope = Literal["finance_collections", "sales_sdr", "general"]

# Department-scoped voice defaults (honest scaffold — org/agent identity overrides win).
_DEFAULT_POLICIES: dict[VoicePolicyScope, dict[str, Any]] = {
    "finance_collections": {
        "recording_consent_required": True,
        "disclosure_script": (
            "This call may be recorded for quality and compliance purposes."
        ),
        "allow_autonomous_writes": False,
        "allow_transfer": True,
        "blocked_tool_patterns": ["calendar.*.create", "calendar.*.book", "stripe.*.create"],
        "allowed_tool_patterns": [
            "calendar.availability.read",
            "twilio.*.get",
            "hubspot.*.get",
        ],
    },
    "sales_sdr": {
        "recording_consent_required": True,
        "disclosure_script": "Hi, this call may be recorded.",
        "allow_autonomous_writes": False,
        "allow_transfer": True,
        "blocked_tool_patterns": [],
        "allowed_tool_patterns": [
            "calendar.availability.read",
            "calendar.events.create",
            "hubspot.contacts.*",
            "apollo.*",
        ],
    },
    "general": {
        "recording_consent_required": False,
        "disclosure_script": None,
        "allow_autonomous_writes": False,
        "allow_transfer": True,
        "blocked_tool_patterns": [],
        "allowed_tool_patterns": [],
    },
}


@dataclass(frozen=True)
class VoicePstnPolicy:
    scope: VoicePolicyScope
    recording_consent_required: bool
    disclosure_script: str | None
    allow_autonomous_writes: bool
    allow_transfer: bool
    blocked_tool_patterns: tuple[str, ...]
    allowed_tool_patterns: tuple[str, ...]
    identity: EffectiveAgentIdentity | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "recording_consent_required": self.recording_consent_required,
            "disclosure_script": self.disclosure_script,
            "allow_autonomous_writes": self.allow_autonomous_writes,
            "allow_transfer": self.allow_transfer,
            "blocked_tool_patterns": list(self.blocked_tool_patterns),
            "allowed_tool_patterns": list(self.allowed_tool_patterns),
            "agent_trust_level": self.identity.trust_level if self.identity else None,
        }


def infer_voice_policy_scope(*, department: str | None, agent_name: str | None) -> VoicePolicyScope:
    dept = (department or "").strip().lower()
    name = (agent_name or "").strip().lower()
    if dept in {"finance", "accounting", "collections"} or "collection" in name:
        return "finance_collections"
    if dept in {"sales", "marketing", "revenue"} or "sdr" in name or "sales" in name:
        return "sales_sdr"
    return "general"


def resolve_voice_pstn_policy(
    client: Any,
    *,
    org_id: str,
    agent_id: str | None,
    department: str | None = None,
    agent_name: str | None = None,
) -> VoicePstnPolicy:
    scope = infer_voice_policy_scope(department=department, agent_name=agent_name)
    base = dict(_DEFAULT_POLICIES[scope])
    identity: EffectiveAgentIdentity | None = None
    if agent_id:
        try:
            identity = resolve_effective_identity(client, org_id, agent_id)
            if identity.allowed_tool_patterns:
                base["allowed_tool_patterns"] = list(identity.allowed_tool_patterns)
            if identity.trust_level == "read_only":
                base["allow_autonomous_writes"] = False
                base["blocked_tool_patterns"] = list(
                    set(base.get("blocked_tool_patterns") or []) | {"*.create", "*.delete"}
                )
        except Exception:  # noqa: BLE001
            identity = None
    return VoicePstnPolicy(
        scope=scope,
        recording_consent_required=bool(base.get("recording_consent_required")),
        disclosure_script=base.get("disclosure_script"),
        allow_autonomous_writes=bool(base.get("allow_autonomous_writes")),
        allow_transfer=bool(base.get("allow_transfer", True)),
        blocked_tool_patterns=tuple(base.get("blocked_tool_patterns") or ()),
        allowed_tool_patterns=tuple(base.get("allowed_tool_patterns") or ()),
        identity=identity,
    )


def enforce_pstn_tool_policy(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    action_name: str,
    policy: VoicePstnPolicy,
    action_kind: str = "read",
) -> None:
    """Mid-call tools pass the same identity gate plus PSTN policy patterns."""
    import fnmatch

    for pattern in policy.blocked_tool_patterns:
        if fnmatch.fnmatch(action_name, pattern):
            raise PermissionError(f"PSTN policy blocks {action_name} for scope {policy.scope}")
    if policy.allowed_tool_patterns:
        if not any(fnmatch.fnmatch(action_name, p) for p in policy.allowed_tool_patterns):
            raise PermissionError(
                f"PSTN policy scope {policy.scope} does not allow {action_name}"
            )
    if policy.identity:
        enforce_agent_identity_before_tool(
            client,
            org_id,
            agent_id,
            tool_name=action_name,
            invoke_action=action_name,
            action_kind=action_kind,
        )
