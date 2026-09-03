"""Agent Identity IAM — governed principal records extending write-authority."""
from __future__ import annotations

import fnmatch
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.agent_tool_permissions import is_persisted_agent_id
from app.workflows.audit import write_audit_event

TrustLevel = Literal["read_only", "write_with_approval", "autonomous"]
ActionKind = Literal["read", "write", "delete"]

AUDIT_AGENT_SPEND_BLOCKED = "agent.identity.spend_limit_blocked"
AUDIT_AGENT_TOOL_DENIED = "agent.identity.tool_denied"
AUDIT_DELEGATION_GRANTED = "agent.delegation.granted"
AUDIT_DELEGATION_USED = "agent.delegation.used"
AUDIT_DELEGATION_REVOKED = "agent.delegation.revoked"

AGENT_SPEND_LIMIT_EXCEEDED = "agent_spend_limit_exceeded"
AGENT_IDENTITY_DENIED = "agent_identity_denied"


class AgentIdentityDeniedError(Exception):
    code = AGENT_IDENTITY_DENIED

    def __init__(self, message: str, *, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.details = dict(details or {})


class AgentSpendLimitExceededError(Exception):
    code = AGENT_SPEND_LIMIT_EXCEEDED

    def __init__(
        self,
        *,
        dimension: str,
        limit: float,
        used: float,
        agent_id: str,
    ) -> None:
        self.dimension = dimension
        self.limit = limit
        self.used = used
        self.agent_id = agent_id
        super().__init__(
            f"Agent {agent_id} spend limit exceeded: {dimension} limit {limit}, used {used}"
        )


@dataclass(frozen=True)
class EffectiveAgentIdentity:
    org_id: str
    agent_id: str
    trust_level: TrustLevel
    allowed_tool_patterns: tuple[str, ...]
    allowed_action_kinds: frozenset[str]
    allowed_data_scopes: tuple[str, ...]
    max_actions_per_day: int | None
    max_tokens_per_day: int | None
    max_spend_usd_per_day: float | None
    can_delegate: bool
    approval_rule_overrides: dict[str, str]
    active_delegation_id: str | None = None


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def get_agent_identity_record(client: Any, org_id: str, agent_id: str) -> dict[str, Any] | None:
    if not is_persisted_agent_id(agent_id):
        return None
    rows = (
        client.table("agent_identity_records")
        .select("*")
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def _active_delegation_for_agent(client: Any, org_id: str, agent_id: str) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    rows = (
        client.table("agent_delegation_grants")
        .select("*")
        .eq("org_id", org_id)
        .eq("grantee_agent_id", agent_id)
        .is_("revoked_at", "null")
        .gt("expires_at", now)
        .order("expires_at", desc=True)
        .limit(1)
        .execute()
        .data
        or []
    )
    return dict(rows[0]) if rows else None


def resolve_effective_identity(
    client: Any,
    org_id: str,
    agent_id: str,
) -> EffectiveAgentIdentity | None:
    if not is_persisted_agent_id(agent_id):
        return None
    record = get_agent_identity_record(client, org_id, agent_id)
    delegation = _active_delegation_for_agent(client, org_id, agent_id)
    if not record and not delegation:
        return None

    trust_level: TrustLevel = "write_with_approval"
    patterns: list[str] = []
    action_kinds = frozenset({"read", "write"})
    data_scopes: list[str] = []
    max_actions: int | None = None
    max_tokens: int | None = None
    max_spend: float | None = None
    can_delegate = False
    overrides: dict[str, str] = {}
    delegation_id: str | None = None

    if record:
        trust_level = str(record.get("trust_level") or "write_with_approval")  # type: ignore[assignment]
        patterns = [str(p) for p in (record.get("allowed_tool_patterns") or []) if str(p).strip()]
        kinds = [str(k).lower() for k in (record.get("allowed_action_kinds") or []) if str(k).strip()]
        if kinds:
            action_kinds = frozenset(kinds)
        data_scopes = [str(s) for s in (record.get("allowed_data_scopes") or []) if str(s).strip()]
        max_actions = _optional_int(record.get("max_actions_per_day"))
        max_tokens = _optional_int(record.get("max_tokens_per_day"))
        max_spend = _optional_float(record.get("max_spend_usd_per_day"))
        can_delegate = bool(record.get("can_delegate"))
        raw_overrides = safe_normalize_stored_dict(record, key="approval_rule_overrides")
        overrides = {str(k): str(v) for k, v in raw_overrides.items() if v}

    if delegation:
        delegation_id = str(delegation.get("id") or "") or None
        perms = safe_normalize_stored_dict(delegation, key="delegated_permissions")
        if perms.get("elevated_trust_level"):
            trust_level = str(perms["elevated_trust_level"])  # type: ignore[assignment]
        extra_patterns = perms.get("extra_tool_patterns")
        if isinstance(extra_patterns, list):
            patterns.extend(str(p) for p in extra_patterns if str(p).strip())
        if perms.get("bypass_spend_limit"):
            max_actions = None
            max_tokens = None
            max_spend = None
        extra_kinds = perms.get("extra_action_kinds")
        if isinstance(extra_kinds, list):
            action_kinds = frozenset(set(action_kinds) | {str(k).lower() for k in extra_kinds})

    return EffectiveAgentIdentity(
        org_id=org_id,
        agent_id=agent_id,
        trust_level=trust_level,
        allowed_tool_patterns=tuple(patterns),
        allowed_action_kinds=action_kinds,
        allowed_data_scopes=tuple(data_scopes),
        max_actions_per_day=max_actions,
        max_tokens_per_day=max_tokens,
        max_spend_usd_per_day=max_spend,
        can_delegate=can_delegate,
        approval_rule_overrides=overrides,
        active_delegation_id=delegation_id,
    )


def tool_matches_patterns(tool_name: str, invoke_action: str, patterns: tuple[str, ...]) -> bool:
    if not patterns:
        return True
    targets = {tool_name, invoke_action, invoke_action.split(".", 1)[0] if "." in invoke_action else invoke_action}
    for pattern in patterns:
        pat = str(pattern or "").strip()
        if not pat:
            continue
        for target in targets:
            if fnmatch.fnmatch(target, pat) or fnmatch.fnmatch(target.lower(), pat.lower()):
                return True
    return False


def get_daily_usage(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    usage_date: date | None = None,
) -> dict[str, float]:
    day = usage_date or _utc_today()
    rows = (
        client.table("agent_identity_usage_daily")
        .select("action_count, token_count, spend_usd")
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .eq("usage_date", day.isoformat())
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return {"actions": 0.0, "tokens": 0.0, "spendUsd": 0.0}
    row = rows[0]
    return {
        "actions": float(row.get("action_count") or 0),
        "tokens": float(row.get("token_count") or 0),
        "spendUsd": round(float(row.get("spend_usd") or 0), 4),
    }


def _would_exceed(limit: int | float | None, used: float, projected: float) -> bool:
    if limit is None:
        return False
    return used + projected > float(limit)


def check_agent_spend_limit(
    client: Any,
    org_id: str,
    agent_id: str,
    identity: EffectiveAgentIdentity,
    *,
    projected_actions: int = 0,
    projected_tokens: int = 0,
    projected_spend_usd: float = 0.0,
) -> None:
    usage = get_daily_usage(client, org_id, agent_id)
    if _would_exceed(identity.max_actions_per_day, usage["actions"], projected_actions):
        raise AgentSpendLimitExceededError(
            dimension="actions",
            limit=float(identity.max_actions_per_day or 0),
            used=usage["actions"],
            agent_id=agent_id,
        )
    if _would_exceed(identity.max_tokens_per_day, usage["tokens"], projected_tokens):
        raise AgentSpendLimitExceededError(
            dimension="tokens",
            limit=float(identity.max_tokens_per_day or 0),
            used=usage["tokens"],
            agent_id=agent_id,
        )
    if _would_exceed(identity.max_spend_usd_per_day, usage["spendUsd"], projected_spend_usd):
        raise AgentSpendLimitExceededError(
            dimension="spend_usd",
            limit=float(identity.max_spend_usd_per_day or 0),
            used=usage["spendUsd"],
            agent_id=agent_id,
        )


def record_agent_usage(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    actions: int = 0,
    tokens: int = 0,
    spend_usd: float = 0.0,
    usage_date: date | None = None,
) -> None:
    if not is_persisted_agent_id(agent_id):
        return
    if actions <= 0 and tokens <= 0 and spend_usd <= 0:
        return
    day = usage_date or _utc_today()
    existing = get_daily_usage(client, org_id, agent_id, usage_date=day)
    payload = {
        "org_id": org_id,
        "agent_id": agent_id,
        "usage_date": day.isoformat(),
        "action_count": int(existing["actions"]) + max(actions, 0),
        "token_count": int(existing["tokens"]) + max(tokens, 0),
        "spend_usd": round(existing["spendUsd"] + max(spend_usd, 0.0), 4),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("agent_identity_usage_daily").upsert(
        payload,
        on_conflict="org_id,agent_id,usage_date",
    ).execute()


def resolve_approval_override(
    identity: EffectiveAgentIdentity | None,
    action_kind: str,
) -> str | None:
    """Return always_approve | always_deny | auto_run | None."""
    if identity is None:
        return None
    override = str(identity.approval_rule_overrides.get(action_kind) or "").strip().lower()
    return override or None


def enforce_agent_identity_before_tool(
    client: Any,
    org_id: str,
    agent_id: str | None,
    *,
    tool_name: str,
    invoke_action: str,
    action_kind: str,
    actor_id: str | None = None,
    projected_spend_usd: float = 0.01,
) -> EffectiveAgentIdentity | None:
    """Raise AgentIdentityDeniedError or AgentSpendLimitExceededError when blocked."""
    if not agent_id or not is_persisted_agent_id(agent_id):
        return None
    identity = resolve_effective_identity(client, org_id, agent_id)
    if identity is None:
        return None

    kind = (action_kind or "write").strip().lower()
    if kind not in identity.allowed_action_kinds:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_AGENT_TOOL_DENIED,
            resource_type="agent",
            resource_id=agent_id,
            metadata={"reason": "action_kind_denied", "action_kind": kind, "tool": tool_name},
        )
        raise AgentIdentityDeniedError(
            f"Agent is not permitted to perform {kind} actions.",
            reason="action_kind_denied",
            details={"action_kind": kind},
        )

    if identity.trust_level == "read_only" and kind in {"write", "delete"}:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_AGENT_TOOL_DENIED,
            resource_type="agent",
            resource_id=agent_id,
            metadata={"reason": "read_only", "tool": tool_name},
        )
        raise AgentIdentityDeniedError(
            "Agent is read-only and cannot perform write actions.",
            reason="read_only",
        )

    if identity.allowed_tool_patterns and not tool_matches_patterns(
        tool_name, invoke_action, identity.allowed_tool_patterns
    ):
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_AGENT_TOOL_DENIED,
            resource_type="agent",
            resource_id=agent_id,
            metadata={"reason": "tool_pattern_denied", "tool": tool_name, "invoke_action": invoke_action},
        )
        raise AgentIdentityDeniedError(
            "This tool is outside the agent's allowed tool scope.",
            reason="tool_pattern_denied",
            details={"tool_name": tool_name, "invoke_action": invoke_action},
        )

    try:
        check_agent_spend_limit(
            client,
            org_id,
            agent_id,
            identity,
            projected_actions=1,
            projected_spend_usd=projected_spend_usd,
        )
    except AgentSpendLimitExceededError as exc:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_AGENT_SPEND_BLOCKED,
            resource_type="agent",
            resource_id=agent_id,
            metadata={
                "dimension": exc.dimension,
                "limit": exc.limit,
                "used": exc.used,
                "tool": tool_name,
            },
        )
        raise

    if identity.active_delegation_id:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_DELEGATION_USED,
            resource_type="agent_delegation_grant",
            resource_id=identity.active_delegation_id,
            metadata={"grantee_agent_id": agent_id, "tool": tool_name},
        )
    return identity


def upsert_agent_identity_record(
    client: Any,
    *,
    org_id: str,
    agent_id: str,
    actor_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "org_id": org_id,
        "agent_id": agent_id,
        "updated_at": now,
    }
    if "departmentId" in payload or "department_id" in payload:
        row["department_id"] = payload.get("departmentId") or payload.get("department_id")
    for key, col in (
        ("agentRole", "agent_role"),
        ("trustLevel", "trust_level"),
        ("canDelegate", "can_delegate"),
    ):
        if key in payload:
            row[col] = payload[key]
        elif col in payload:
            row[col] = payload[col]
    for key, col in (
        ("allowedToolPatterns", "allowed_tool_patterns"),
        ("allowedActionKinds", "allowed_action_kinds"),
        ("allowedDataScopes", "allowed_data_scopes"),
    ):
        val = payload.get(key) if key in payload else payload.get(col)
        if val is not None:
            row[col] = list(val)
    for key, col in (
        ("maxActionsPerDay", "max_actions_per_day"),
        ("maxTokensPerDay", "max_tokens_per_day"),
    ):
        val = payload.get(key) if key in payload else payload.get(col)
        if val is not None:
            row[col] = _optional_int(val)
    for key, col in (("maxSpendUsdPerDay", "max_spend_usd_per_day"),):
        val = payload.get(key) if key in payload else payload.get(col)
        if val is not None:
            row[col] = _optional_float(val)
    if "approvalRuleOverrides" in payload or "approval_rule_overrides" in payload:
        overrides = payload.get("approvalRuleOverrides") or payload.get("approval_rule_overrides") or {}
        row["approval_rule_overrides"] = dict(overrides) if isinstance(overrides, dict) else {}

    existing = get_agent_identity_record(client, org_id, agent_id)
    if existing:
        updated = (
            client.table("agent_identity_records")
            .update(row)
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .execute()
        )
        data = (updated.data or [existing])[0]
    else:
        row["created_at"] = now
        row["id"] = str(uuid.uuid4())
        inserted = client.table("agent_identity_records").insert(row).execute()
        data = (inserted.data or [row])[0]

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="agent.identity.updated",
        resource_type="agent",
        resource_id=agent_id,
        metadata={"trust_level": data.get("trust_level")},
    )
    return dict(data)


def create_delegation_grant(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    grantor_agent_id: str | None,
    grantee_agent_id: str | None,
    grantee_user_id: str | None,
    delegated_permissions: dict[str, Any],
    reason: str | None,
    expires_at: str,
) -> dict[str, Any]:
    if not grantee_agent_id and not grantee_user_id:
        raise ValueError("grantee_agent_id or grantee_user_id required")
    row = {
        "id": str(uuid.uuid4()),
        "org_id": org_id,
        "grantor_agent_id": grantor_agent_id,
        "grantor_user_id": actor_id,
        "grantee_agent_id": grantee_agent_id,
        "grantee_user_id": grantee_user_id,
        "delegated_permissions": dict(delegated_permissions or {}),
        "reason": reason,
        "expires_at": expires_at,
        "created_by": actor_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    inserted = client.table("agent_delegation_grants").insert(row).execute()
    data = (inserted.data or [row])[0]
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_DELEGATION_GRANTED,
        resource_type="agent_delegation_grant",
        resource_id=str(data.get("id")),
        metadata={"grantee_agent_id": grantee_agent_id, "expires_at": expires_at},
    )
    return dict(data)


def revoke_delegation_grant(
    client: Any,
    *,
    org_id: str,
    grant_id: str,
    actor_id: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    updated = (
        client.table("agent_delegation_grants")
        .update({"revoked_at": now})
        .eq("org_id", org_id)
        .eq("id", grant_id)
        .execute()
    )
    data = (updated.data or [None])[0]
    if not data:
        raise LookupError("Delegation grant not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_DELEGATION_REVOKED,
        resource_type="agent_delegation_grant",
        resource_id=grant_id,
    )
    return dict(data)


def list_delegation_grants(client: Any, org_id: str, *, agent_id: str | None = None) -> list[dict[str, Any]]:
    query = client.table("agent_delegation_grants").select("*").eq("org_id", org_id)
    if agent_id:
        query = query.eq("grantee_agent_id", agent_id)
    rows = query.order("created_at", desc=True).limit(50).execute().data or []
    return [dict(r) for r in rows]


def build_identity_status(client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
    record = get_agent_identity_record(client, org_id, agent_id)
    identity = resolve_effective_identity(client, org_id, agent_id)
    usage = get_daily_usage(client, org_id, agent_id)
    return {
        "record": record,
        "effective": {
            "trustLevel": identity.trust_level if identity else None,
            "allowedToolPatterns": list(identity.allowed_tool_patterns) if identity else [],
            "allowedActionKinds": sorted(identity.allowed_action_kinds) if identity else [],
            "activeDelegationId": identity.active_delegation_id if identity else None,
        },
        "usageToday": usage,
        "usageDate": _utc_today().isoformat(),
    }


def serialize_identity_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "orgId": str(row.get("org_id") or ""),
        "agentId": str(row.get("agent_id") or ""),
        "departmentId": str(row.get("department_id") or "") or None,
        "agentRole": row.get("agent_role"),
        "trustLevel": row.get("trust_level"),
        "allowedToolPatterns": list(row.get("allowed_tool_patterns") or []),
        "allowedActionKinds": list(row.get("allowed_action_kinds") or []),
        "allowedDataScopes": list(row.get("allowed_data_scopes") or []),
        "maxActionsPerDay": row.get("max_actions_per_day"),
        "maxTokensPerDay": row.get("max_tokens_per_day"),
        "maxSpendUsdPerDay": row.get("max_spend_usd_per_day"),
        "canDelegate": bool(row.get("can_delegate")),
        "approvalRuleOverrides": safe_normalize_stored_dict(row, key="approval_rule_overrides"),
        "updatedAt": row.get("updated_at"),
    }
