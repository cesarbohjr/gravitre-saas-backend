"""Autonomous run budgets — daily caps on actions, tokens, and spend (STA-109)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from app.workflows.audit import write_audit_event
from app.core.safe_dict import safe_normalize_stored_dict

BudgetDimension = Literal["actions", "tokens", "spend_usd"]

AUDIT_BUDGET_BLOCKED = "operator.auto_execute.budget_blocked"

# Rough USD estimate when only credits are known (matches enterprise cost views).
ESTIMATED_USD_PER_CREDIT = 0.01


class AutonomousBudgetExceededError(Exception):
    """Raised when an autonomous run would exceed a configured daily cap."""

    code = "AUTONOMOUS_BUDGET_EXCEEDED"

    def __init__(
        self,
        *,
        dimension: BudgetDimension,
        limit: float,
        used: float,
        operator_id: str,
    ) -> None:
        self.dimension = dimension
        self.limit = limit
        self.used = used
        self.operator_id = operator_id
        super().__init__(
            f"Autonomous run budget exceeded for operator {operator_id}: "
            f"{dimension} daily limit {limit}, current usage {used}"
        )


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    row = (
        client.table("organizations")
        .select("settings")
        .eq("id", org_id)
        .limit(1)
        .execute()
        .data
    )
    if not row:
        return {}
    settings = row[0].get("settings")
    return settings if isinstance(settings, dict) else {}


def get_org_autonomous_budget_defaults(client: Any, org_id: str) -> dict[str, float | None]:
    enterprise = _org_settings(client, org_id).get("enterprise")
    if not isinstance(enterprise, dict):
        return {"maxActionsPerDay": None, "maxTokensPerDay": None, "maxSpendUsdPerDay": None}
    raw = enterprise.get("autonomousRunBudgets")
    if not isinstance(raw, dict):
        return {"maxActionsPerDay": None, "maxTokensPerDay": None, "maxSpendUsdPerDay": None}
    return {
        "maxActionsPerDay": _optional_int(raw.get("maxActionsPerDay")),
        "maxTokensPerDay": _optional_int(raw.get("maxTokensPerDay")),
        "maxSpendUsdPerDay": _optional_float(raw.get("maxSpendUsdPerDay")),
    }


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


def get_effective_budgets(client: Any, org_id: str, operator: dict[str, Any]) -> dict[str, int | float | None]:
    org_defaults = get_org_autonomous_budget_defaults(client, org_id)
    return {
        "maxActionsPerDay": _optional_int(operator.get("auto_run_max_actions_per_day"))
        if operator.get("auto_run_max_actions_per_day") is not None
        else org_defaults["maxActionsPerDay"],
        "maxTokensPerDay": _optional_int(operator.get("auto_run_max_tokens_per_day"))
        if operator.get("auto_run_max_tokens_per_day") is not None
        else org_defaults["maxTokensPerDay"],
        "maxSpendUsdPerDay": _optional_float(operator.get("auto_run_max_spend_usd_per_day"))
        if operator.get("auto_run_max_spend_usd_per_day") is not None
        else org_defaults["maxSpendUsdPerDay"],
    }


def get_daily_usage(
    client: Any,
    org_id: str,
    operator_id: str,
    *,
    usage_date: date | None = None,
) -> dict[str, float]:
    day = usage_date or _utc_today()
    rows = (
        client.table("operator_autonomous_usage_daily")
        .select("action_count, token_count, spend_usd")
        .eq("org_id", org_id)
        .eq("operator_id", operator_id)
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


def check_autonomous_budget(
    client: Any,
    org_id: str,
    operator: dict[str, Any],
    *,
    projected_actions: int = 0,
    projected_tokens: int = 0,
    projected_spend_usd: float = 0.0,
) -> None:
    """Raise AutonomousBudgetExceededError when a projected increment exceeds caps."""
    operator_id = str(operator["id"])
    budgets = get_effective_budgets(client, org_id, operator)
    usage = get_daily_usage(client, org_id, operator_id)

    if _would_exceed(budgets["maxActionsPerDay"], usage["actions"], projected_actions):
        raise AutonomousBudgetExceededError(
            dimension="actions",
            limit=float(budgets["maxActionsPerDay"] or 0),
            used=usage["actions"],
            operator_id=operator_id,
        )
    if _would_exceed(budgets["maxTokensPerDay"], usage["tokens"], projected_tokens):
        raise AutonomousBudgetExceededError(
            dimension="tokens",
            limit=float(budgets["maxTokensPerDay"] or 0),
            used=usage["tokens"],
            operator_id=operator_id,
        )
    if _would_exceed(budgets["maxSpendUsdPerDay"], usage["spendUsd"], projected_spend_usd):
        raise AutonomousBudgetExceededError(
            dimension="spend_usd",
            limit=float(budgets["maxSpendUsdPerDay"] or 0),
            used=usage["spendUsd"],
            operator_id=operator_id,
        )


def record_autonomous_usage(
    client: Any,
    org_id: str,
    operator_id: str,
    *,
    actions: int = 0,
    tokens: int = 0,
    spend_usd: float = 0.0,
    usage_date: date | None = None,
) -> None:
    if actions <= 0 and tokens <= 0 and spend_usd <= 0:
        return
    day = usage_date or _utc_today()
    existing = get_daily_usage(client, org_id, operator_id, usage_date=day)
    payload = {
        "org_id": org_id,
        "operator_id": operator_id,
        "usage_date": day.isoformat(),
        "action_count": int(existing["actions"]) + max(actions, 0),
        "token_count": int(existing["tokens"]) + max(tokens, 0),
        "spend_usd": round(existing["spendUsd"] + max(spend_usd, 0.0), 4),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client.table("operator_autonomous_usage_daily").upsert(
        payload,
        on_conflict="org_id,operator_id,usage_date",
    ).execute()


def enforce_autonomous_tool_budget(
    client: Any,
    org_id: str,
    operator_id: str,
    *,
    actor_id: str | None = None,
) -> None:
    """Check tool-call budget and record one action after the check passes."""
    operator = (
        client.table("operators")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", operator_id)
        .limit(1)
        .execute()
        .data
    )
    if not operator:
        return
    op = operator[0]
    mode = str(op.get("execution_mode") or "plan_only")
    if mode == "plan_only":
        return
    try:
        check_autonomous_budget(client, org_id, op, projected_actions=1)
    except AutonomousBudgetExceededError as exc:
        write_audit_event(
            client,
            org_id=org_id,
            actor_id=actor_id,
            action=AUDIT_BUDGET_BLOCKED,
            resource_type="operator",
            resource_id=operator_id,
            metadata={
                "dimension": exc.dimension,
                "limit": exc.limit,
                "used": exc.used,
                "source": "tool_invoke",
            },
        )
        raise
    record_autonomous_usage(client, org_id, operator_id, actions=1)


def update_operator_run_budgets(
    client: Any,
    *,
    org_id: str,
    operator_id: str,
    max_actions_per_day: int | None = None,
    max_tokens_per_day: int | None = None,
    max_spend_usd_per_day: float | None = None,
    actor_id: str,
    unset: set[str] | None = None,
) -> dict[str, Any]:
    unset = unset or set()
    payload: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if "maxActionsPerDay" in unset:
        payload["auto_run_max_actions_per_day"] = None
    elif max_actions_per_day is not None:
        payload["auto_run_max_actions_per_day"] = max_actions_per_day
    if "maxTokensPerDay" in unset:
        payload["auto_run_max_tokens_per_day"] = None
    elif max_tokens_per_day is not None:
        payload["auto_run_max_tokens_per_day"] = max_tokens_per_day
    if "maxSpendUsdPerDay" in unset:
        payload["auto_run_max_spend_usd_per_day"] = None
    elif max_spend_usd_per_day is not None:
        payload["auto_run_max_spend_usd_per_day"] = round(float(max_spend_usd_per_day), 4)

    updated = (
        client.table("operators")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", operator_id)
        .execute()
    )
    if not updated.data:
        raise ValueError("Operator not found")
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="operator.auto_execute.budgets_updated",
        resource_type="operator",
        resource_id=operator_id,
        metadata={
            "maxActionsPerDay": updated.data[0].get("auto_run_max_actions_per_day"),
            "maxTokensPerDay": updated.data[0].get("auto_run_max_tokens_per_day"),
            "maxSpendUsdPerDay": updated.data[0].get("auto_run_max_spend_usd_per_day"),
        },
    )
    return dict(updated.data[0])


def build_budget_status(client: Any, org_id: str, operator: dict[str, Any]) -> dict[str, Any]:
    operator_id = str(operator["id"])
    limits = get_effective_budgets(client, org_id, operator)
    usage = get_daily_usage(client, org_id, operator_id)
    return {
        "limits": limits,
        "usageToday": usage,
        "usageDate": _utc_today().isoformat(),
    }


def credits_to_estimated_usd(credits: int) -> float:
    return round(max(int(credits or 0), 0) * ESTIMATED_USD_PER_CREDIT, 4)


def is_autonomous_operator(operator: dict[str, Any]) -> bool:
    from app.operators.services.auto_execute_service import get_execution_mode

    return get_execution_mode(operator) != "plan_only"


def record_autonomous_llm_usage(
    client: Any,
    org_id: str,
    operator_id: str,
    *,
    input_tokens: int,
    output_tokens: int,
    spend_usd: float,
) -> None:
    tokens = max(int(input_tokens or 0), 0) + max(int(output_tokens or 0), 0)
    record_autonomous_usage(
        client,
        org_id,
        operator_id,
        tokens=tokens,
        spend_usd=round(float(spend_usd or 0), 4),
    )


def check_autonomous_llm_budget(
    client: Any,
    org_id: str,
    operator: dict[str, Any],
    *,
    projected_tokens: int,
    projected_spend_usd: float,
) -> None:
    check_autonomous_budget(
        client,
        org_id,
        operator,
        projected_tokens=projected_tokens,
        projected_spend_usd=projected_spend_usd,
    )


def update_org_autonomous_budget_defaults(
    client: Any,
    *,
    org_id: str,
    max_actions_per_day: int | None = None,
    max_tokens_per_day: int | None = None,
    max_spend_usd_per_day: float | None = None,
    actor_id: str,
    unset: set[str] | None = None,
) -> dict[str, float | int | None]:
    unset = unset or set()
    settings = _org_settings(client, org_id)
    enterprise = safe_normalize_stored_dict(settings, key="enterprise")
    budgets = safe_normalize_stored_dict(enterprise, key="autonomousRunBudgets")

    if "maxActionsPerDay" in unset:
        budgets.pop("maxActionsPerDay", None)
    elif max_actions_per_day is not None:
        budgets["maxActionsPerDay"] = max_actions_per_day
    if "maxTokensPerDay" in unset:
        budgets.pop("maxTokensPerDay", None)
    elif max_tokens_per_day is not None:
        budgets["maxTokensPerDay"] = max_tokens_per_day
    if "maxSpendUsdPerDay" in unset:
        budgets.pop("maxSpendUsdPerDay", None)
    elif max_spend_usd_per_day is not None:
        budgets["maxSpendUsdPerDay"] = round(float(max_spend_usd_per_day), 4)

    enterprise["autonomousRunBudgets"] = budgets
    settings["enterprise"] = enterprise
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action="enterprise.autonomous_run_budgets.updated",
        resource_type="organization",
        resource_id=org_id,
        metadata={"autonomousRunBudgets": budgets},
    )
    return get_org_autonomous_budget_defaults(client, org_id)


def list_operator_budget_statuses(client: Any, org_id: str) -> list[dict[str, Any]]:
    from app.operators.repository import list_operators

    rows: list[dict[str, Any]] = []
    for operator in list_operators(client, org_id):
        status = build_budget_status(client, org_id, operator)
        rows.append(
            {
                "agentId": str(operator["id"]),
                "name": operator.get("name") or "",
                "executionMode": operator.get("execution_mode") or "plan_only",
                **status,
            }
        )
    return rows
