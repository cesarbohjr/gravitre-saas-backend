"""Enforce the "Slow down" and "Workspace limits" safety rules chosen for an agent.

Both are saved as names in ``agents.guardrails`` (the creator's labels), with optional
numbers under ``agents.config.guardrail_limits``:

- **Slow down** (``rate-limit``): at most ``max_actions_per_hour`` tool calls per hour
  (default 60), counted per agent across chat, jobs, workflows and voice.
- **Workspace limits** (``env-restrict``): in the live workspace (production) the agent
  may only read; changes are allowed in test workspaces such as staging.

``invoke_tool`` calls :func:`enforce_agent_guardrail_limits` for every tool call made on
behalf of a saved agent.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

RATE_LIMIT_KEYS = {"rate-limit", "rate_limit", "slow down"}
WORKSPACE_LIMIT_KEYS = {"env-restrict", "env_restrict", "workspace limits"}
DEFAULT_MAX_ACTIONS_PER_HOUR = 60
MAX_ACTIONS_PER_HOUR_CEILING = 10_000
LIVE_ENVIRONMENTS = frozenset({"production"})

_CACHE_TTL_S = 30.0
_cache: dict[tuple[str, str], tuple[float, "AgentLimits"]] = {}
_cache_lock = Lock()


class AgentGuardrailLimitError(Exception):
    def __init__(self, message: str, *, code: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class AgentLimits:
    max_actions_per_hour: int | None = None
    live_read_only: bool = False

    @property
    def active(self) -> bool:
        return self.max_actions_per_hour is not None or self.live_read_only


def _guardrail_keys(raw: Any) -> set[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    keys: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            item = item.get("id") or item.get("name")
        text = str(item or "").strip().lower()
        if text:
            keys.add(text)
    return keys


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return min(number, MAX_ACTIONS_PER_HOUR_CEILING)


def resolve_agent_limits(agent: dict[str, Any] | None) -> AgentLimits:
    """Turn an agent row's guardrails and config into enforceable limits."""
    if not isinstance(agent, dict):
        return AgentLimits()
    keys = _guardrail_keys(agent.get("guardrails"))
    config = safe_normalize_stored_dict(agent.get("config"))
    limits_cfg = safe_normalize_stored_dict(config, key="guardrail_limits")
    max_per_hour: int | None = None
    if keys & RATE_LIMIT_KEYS:
        max_per_hour = _positive_int(limits_cfg.get("max_actions_per_hour")) or DEFAULT_MAX_ACTIONS_PER_HOUR
    return AgentLimits(
        max_actions_per_hour=max_per_hour,
        live_read_only=bool(keys & WORKSPACE_LIMIT_KEYS),
    )


def load_agent_limits(client: Any, org_id: str, agent_id: str) -> AgentLimits:
    """Read limits for a saved agent, cached briefly so each tool call isn't a query."""
    cache_key = (str(org_id), str(agent_id))
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _CACHE_TTL_S:
            return hit[1]
    limits = AgentLimits()
    try:
        res = (
            client.table("agents")
            .select("guardrails,config")
            .eq("org_id", org_id)
            .eq("id", agent_id)
            .limit(1)
            .execute()
        )
        rows = getattr(res, "data", None) or []
        if rows:
            limits = resolve_agent_limits(rows[0])
    except Exception as exc:  # noqa: BLE001 - a lookup failure must not block tools
        logger.warning("agent_guardrail_limits lookup failed agent=%s error=%s", agent_id, exc)
        return limits
    with _cache_lock:
        _cache[cache_key] = (now, limits)
    return limits


def clear_agent_limits_cache() -> None:
    with _cache_lock:
        _cache.clear()


def is_live_environment(environment_name: str | None) -> bool:
    from app.connectors.constants import normalize_environment_name

    return normalize_environment_name(environment_name) in LIVE_ENVIRONMENTS


def action_is_write(action: str) -> bool:
    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    return invoke_action_requires_write_approval(action)


def check_agent_limits(
    limits: AgentLimits,
    *,
    org_id: str,
    agent_id: str,
    action: str,
    environment_name: str | None,
) -> None:
    """Raise :class:`AgentGuardrailLimitError` when ``action`` breaks a limit.

    The workspace rule is checked first so a blocked change doesn't use up the hourly budget.
    """
    if limits.live_read_only and is_live_environment(environment_name) and action_is_write(action):
        raise AgentGuardrailLimitError(
            "This agent has Workspace limits on, so it can only read in the live workspace. "
            "Run it in a test workspace to make changes, or turn the rule off.",
            code="AGENT_LIVE_WORKSPACE_READ_ONLY",
        )
    if limits.max_actions_per_hour:
        from app.core.rate_limiter import get_rate_limiter

        outcome = get_rate_limiter().check_sync(
            f"agent-actions:{org_id}:{agent_id}",
            limits.max_actions_per_hour,
            3600,
        )
        if not outcome.get("allowed", True):
            retry_after = outcome.get("retry_after")
            minutes = max(1, int((retry_after or 3600) + 59) // 60)
            raise AgentGuardrailLimitError(
                f"This agent reached its limit of {limits.max_actions_per_hour} actions per hour. "
                f"It can act again in about {minutes} min.",
                code="AGENT_RATE_LIMITED",
                retry_after=retry_after,
            )


def enforce_agent_guardrail_limits(ctx: Any, action: str) -> None:
    """Check a tool call made for a saved agent against that agent's limits."""
    from app.services.agent_tool_permissions import is_persisted_agent_id

    agent_id = getattr(ctx, "agent_id", None)
    if not agent_id or not is_persisted_agent_id(agent_id):
        return
    limits = load_agent_limits(ctx.client, ctx.org_id, str(agent_id))
    if not limits.active:
        return
    check_agent_limits(
        limits,
        org_id=str(ctx.org_id),
        agent_id=str(agent_id),
        action=action,
        environment_name=getattr(ctx, "environment_name", None),
    )
