"""Atomic budget reservations for autonomous LLM calls (Task #5).

Problem: check_autonomous_llm_budget() + record_autonomous_llm_usage() has a
TOCTOU race — two concurrent calls can each pass the check and together exceed
the daily cap.

Solution: Redis-backed atomic reservation.
  1. Before the provider call: atomically INCRBYFLOAT the reservation counter
     for (org_id, operator_id, today). If the new total exceeds the cap,
     DECRBYFLOAT (rollback) and raise AutonomousBudgetExceededError.
  2. After the call: replace the estimate with the real usage (net delta).
  3. On error: release the reserved amount.

Each reservation key has a 26-hour TTL so Redis auto-cleans by EOD+2h.

Fallback: when Redis is unavailable we fall back to the Supabase-only path
(the existing check+record pattern). This is explicitly logged so the
degradation is visible in ops dashboards.

Redis key schema:
  gravitre:autobudget:{org_id}:{operator_id}:{dimension}:{YYYY-MM-DD}
  value: float (cumulative reserved + recorded spend)
  TTL:   93600 seconds (26 hours)
"""
from __future__ import annotations

import contextlib
from datetime import date, datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.autonomous_budget_service import (
    AutonomousBudgetExceededError,
    check_autonomous_budget,
    get_effective_budgets,
    record_autonomous_usage,
)

logger = get_logger(__name__)

_KEY_TTL_SECONDS = 93_600   # 26 hours
_KEY_PREFIX = "gravitre:autobudget"


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _reservation_key(org_id: str, operator_id: str, dimension: str, day: date) -> str:
    return f"{_KEY_PREFIX}:{org_id}:{operator_id}:{dimension}:{day.isoformat()}"


def _get_redis(settings: Any) -> Any | None:
    try:
        from app.core.redis_client import get_sync_redis
        return get_sync_redis(settings)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Core reservation: reserve → call → reconcile / release
# ---------------------------------------------------------------------------


class BudgetReservation:
    """Context manager that reserves budget before a call and reconciles after.

    Usage:
        async with BudgetReservation(
            client, settings, org_id, operator_row,
            projected_tokens=est_in + est_out,
            projected_spend_usd=est_spend,
        ) as reservation:
            response = await provider_call(...)
            reservation.actual_tokens = response.input_tokens + response.output_tokens
            reservation.actual_spend_usd = response.cost_usd

    Raises AutonomousBudgetExceededError before entering the block if the
    projected usage would exceed the daily cap.
    """

    def __init__(
        self,
        client: Any,
        settings: Any,
        org_id: str,
        operator: dict[str, Any],
        *,
        projected_tokens: int = 0,
        projected_spend_usd: float = 0.0,
    ) -> None:
        self._client = client
        self._settings = settings
        self._org_id = org_id
        self._operator = operator
        self._operator_id = str(operator["id"])
        self._projected_tokens = max(int(projected_tokens or 0), 0)
        self._projected_spend_usd = max(float(projected_spend_usd or 0.0), 0.0)

        # Filled in by caller after the provider call.
        self.actual_tokens: int = self._projected_tokens
        self.actual_spend_usd: float = self._projected_spend_usd

        self._redis: Any | None = None
        self._reserved: dict[str, float] = {}   # dimension → amount reserved in Redis
        self._day = _utc_today()

    async def __aenter__(self) -> "BudgetReservation":
        await self._reserve()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._reconcile(failed=exc_type is not None)

    # ------------------------------------------------------------------

    async def _reserve(self) -> None:
        import asyncio

        self._redis = _get_redis(self._settings)

        if self._redis is not None:
            await asyncio.to_thread(self._redis_reserve)
        else:
            # Degrade to legacy check-only path (still holds the logical race,
            # but is functionally acceptable when Redis is down).
            logger.warning(
                "budget_reservation_redis_unavailable org_id=%s operator_id=%s "
                "falling back to check-only",
                self._org_id, self._operator_id,
            )
            import asyncio as _asyncio
            await _asyncio.to_thread(
                check_autonomous_budget,
                self._client,
                self._org_id,
                self._operator,
                projected_tokens=self._projected_tokens,
                projected_spend_usd=self._projected_spend_usd,
            )

    def _redis_reserve(self) -> None:
        """Atomically increment reservation counters; roll back on cap breach."""
        redis = self._redis
        budgets = get_effective_budgets(self._client, self._org_id, self._operator)

        reservations_to_make: list[tuple[str, float, float | None]] = []
        # (dimension_key, amount, cap_or_None)

        if self._projected_tokens > 0:
            reservations_to_make.append(
                ("tokens", float(self._projected_tokens), float(budgets["maxTokensPerDay"]) if budgets["maxTokensPerDay"] is not None else None)
            )
        if self._projected_spend_usd > 0:
            reservations_to_make.append(
                ("spend_usd", self._projected_spend_usd, float(budgets["maxSpendUsdPerDay"]) if budgets["maxSpendUsdPerDay"] is not None else None)
            )

        made: list[tuple[str, float]] = []

        for dim, amount, cap in reservations_to_make:
            key = _reservation_key(self._org_id, self._operator_id, dim, self._day)
            try:
                new_total = float(redis.incrbyfloat(key, amount))
                redis.expire(key, _KEY_TTL_SECONDS)
            except Exception as exc:  # noqa: BLE001
                logger.warning("budget_reservation_redis_incr_failed dim=%s error=%s", dim, exc)
                # Roll back everything made so far and degrade.
                self._rollback_made(redis, made)
                return  # degrade — allow the call (Redis failure is non-fatal)

            made.append((dim, amount))
            self._reserved[dim] = amount

            if cap is not None and new_total > cap:
                # Roll back this one and everything before it.
                self._rollback_made(redis, made)
                self._reserved.clear()
                raise AutonomousBudgetExceededError(
                    dimension="tokens" if dim == "tokens" else "spend_usd",
                    limit=cap,
                    used=new_total - amount,
                    operator_id=self._operator_id,
                )

    def _rollback_made(self, redis: Any, made: list[tuple[str, float]]) -> None:
        for dim, amount in made:
            key = _reservation_key(self._org_id, self._operator_id, dim, self._day)
            with contextlib.suppress(Exception):
                redis.incrbyfloat(key, -amount)

    async def _reconcile(self, failed: bool) -> None:
        import asyncio

        actual_tokens = 0 if failed else max(int(self.actual_tokens or 0), 0)
        actual_spend = 0.0 if failed else max(float(self.actual_spend_usd or 0.0), 0.0)

        # Adjust Redis reservation to reflect actual usage (delta correction).
        if self._redis is not None and self._reserved:
            await asyncio.to_thread(self._redis_reconcile, actual_tokens, actual_spend, failed)

        # Always record actual usage in Supabase (source of truth).
        if not failed and (actual_tokens > 0 or actual_spend > 0):
            await asyncio.to_thread(
                record_autonomous_usage,
                self._client,
                self._org_id,
                self._operator_id,
                tokens=actual_tokens,
                spend_usd=actual_spend,
                # actions not tracked here — tool calls record their own action counts
            )

    def _redis_reconcile(self, actual_tokens: int, actual_spend: float, failed: bool) -> None:
        redis = self._redis
        for dim, reserved in self._reserved.items():
            actual = 0.0 if failed else (float(actual_tokens) if dim == "tokens" else actual_spend)
            delta = actual - reserved   # negative → over-reserved, release
            if abs(delta) > 1e-9:
                key = _reservation_key(self._org_id, self._operator_id, dim, self._day)
                with contextlib.suppress(Exception):
                    redis.incrbyfloat(key, delta)


# ---------------------------------------------------------------------------
# Standalone reservation check (no context manager, for callers that need
# explicit acquire/release control, e.g. tool_service.py's approve flow)
# ---------------------------------------------------------------------------


def atomic_reserve_action(
    redis: Any | None,
    org_id: str,
    operator_id: str,
    cap: int | float | None,
) -> float | None:
    """Atomically increment the action counter by 1.

    Returns the new total on success, or None when Redis is unavailable.
    Raises AutonomousBudgetExceededError and rolls back when cap is exceeded.
    """
    if redis is None:
        return None

    day = _utc_today()
    key = _reservation_key(org_id, operator_id, "actions", day)
    try:
        new_total = float(redis.incrbyfloat(key, 1.0))
        redis.expire(key, _KEY_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.warning("atomic_reserve_action_failed org_id=%s error=%s", org_id, exc)
        return None

    if cap is not None and new_total > float(cap):
        with contextlib.suppress(Exception):
            redis.incrbyfloat(key, -1.0)
        raise AutonomousBudgetExceededError(
            dimension="actions",
            limit=float(cap),
            used=new_total - 1.0,
            operator_id=operator_id,
        )
    return new_total


def release_action_reservation(
    redis: Any | None,
    org_id: str,
    operator_id: str,
) -> None:
    """Roll back an action reservation (call on tool failure)."""
    if redis is None:
        return
    day = _utc_today()
    key = _reservation_key(org_id, operator_id, "actions", day)
    with contextlib.suppress(Exception):
        redis.incrbyfloat(key, -1.0)
