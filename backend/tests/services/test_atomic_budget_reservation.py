"""Unit tests for atomic budget reservations (Task #5).

Tests the Redis-backed INCRBYFLOAT reservation pattern in
app/services/budget_reservation.py without touching Supabase or a real
Redis instance.

Run:
    PYTHONPATH=backend python -m pytest backend/tests/services/test_atomic_budget_reservation.py -x -q --noconftest
"""
from __future__ import annotations

import contextlib
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch, call as mock_call

import pytest


# ---------------------------------------------------------------------------
# Helpers & stubs
# ---------------------------------------------------------------------------

ORG_ID = "org-aaa"
OP_ID = "op-bbb"
TODAY = date(2026, 10, 16)


def _mock_operator(
    *,
    actions_cap: int | None = None,
    tokens_cap: int | None = None,
    spend_cap: float | None = None,
) -> dict[str, Any]:
    return {
        "id": OP_ID,
        "auto_run_max_actions_per_day": actions_cap,
        "auto_run_max_tokens_per_day": tokens_cap,
        "auto_run_max_spend_usd_per_day": spend_cap,
    }


def _mock_redis(*, incr_returns: list[float] | None = None) -> MagicMock:
    """Returns a mock Redis client whose incrbyfloat returns `incr_returns` in sequence."""
    redis = MagicMock()
    values = list(incr_returns or [])
    redis.incrbyfloat.side_effect = values if values else [lambda *a, **k: 0.0]
    return redis


def _make_budgets(
    *,
    tokens_cap: int | None,
    spend_cap: float | None,
    actions_cap: int | None = None,
) -> dict[str, Any]:
    return {
        "maxActionsPerDay": actions_cap,
        "maxTokensPerDay": tokens_cap,
        "maxSpendUsdPerDay": spend_cap,
    }


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.services.budget_reservation import (
    BudgetReservation,
    _reservation_key,
    _KEY_TTL_SECONDS,
    atomic_reserve_action,
    release_action_reservation,
)
from app.services.autonomous_budget_service import AutonomousBudgetExceededError


# ---------------------------------------------------------------------------
# _reservation_key
# ---------------------------------------------------------------------------

def test_reservation_key_format():
    key = _reservation_key(ORG_ID, OP_ID, "tokens", TODAY)
    assert key == f"gravitre:autobudget:{ORG_ID}:{OP_ID}:tokens:{TODAY.isoformat()}"


def test_reservation_key_different_dims():
    k1 = _reservation_key(ORG_ID, OP_ID, "tokens", TODAY)
    k2 = _reservation_key(ORG_ID, OP_ID, "spend_usd", TODAY)
    k3 = _reservation_key(ORG_ID, OP_ID, "actions", TODAY)
    assert k1 != k2 != k3
    assert all("gravitre:autobudget:" in k for k in [k1, k2, k3])


# ---------------------------------------------------------------------------
# atomic_reserve_action
# ---------------------------------------------------------------------------

class TestAtomicReserveAction:

    def test_returns_none_when_redis_is_none(self):
        result = atomic_reserve_action(None, ORG_ID, OP_ID, cap=100)
        assert result is None

    def test_increments_and_returns_total(self):
        redis = MagicMock()
        redis.incrbyfloat.return_value = 5.0
        result = atomic_reserve_action(redis, ORG_ID, OP_ID, cap=100)
        assert result == 5.0
        redis.incrbyfloat.assert_called_once()
        redis.expire.assert_called_once()

    def test_no_cap_always_succeeds(self):
        redis = MagicMock()
        redis.incrbyfloat.return_value = 999.0
        result = atomic_reserve_action(redis, ORG_ID, OP_ID, cap=None)
        assert result == 999.0
        # Should NOT have rolled back
        assert redis.incrbyfloat.call_count == 1

    def test_exceeds_cap_rolls_back_and_raises(self):
        redis = MagicMock()
        redis.incrbyfloat.side_effect = [11.0, None]  # first incr returns 11, rollback returns None
        with pytest.raises(AutonomousBudgetExceededError) as exc_info:
            atomic_reserve_action(redis, ORG_ID, OP_ID, cap=10)
        err = exc_info.value
        assert err.dimension == "actions"
        assert err.limit == 10.0
        assert err.used == 10.0  # 11 - 1
        # Rollback: second incrbyfloat call with -1
        assert redis.incrbyfloat.call_count == 2
        rollback_call = redis.incrbyfloat.call_args_list[1]
        assert rollback_call.args[1] == -1.0

    def test_redis_error_returns_none_gracefully(self):
        redis = MagicMock()
        redis.incrbyfloat.side_effect = ConnectionError("redis down")
        result = atomic_reserve_action(redis, ORG_ID, OP_ID, cap=10)
        assert result is None  # degraded, not raised


# ---------------------------------------------------------------------------
# release_action_reservation
# ---------------------------------------------------------------------------

class TestReleaseActionReservation:

    def test_noop_when_redis_none(self):
        # Should not raise
        release_action_reservation(None, ORG_ID, OP_ID)

    def test_decrements_by_one(self):
        redis = MagicMock()
        release_action_reservation(redis, ORG_ID, OP_ID)
        redis.incrbyfloat.assert_called_once()
        args = redis.incrbyfloat.call_args.args
        assert args[1] == -1.0

    def test_redis_error_suppressed(self):
        redis = MagicMock()
        redis.incrbyfloat.side_effect = ConnectionError("redis down")
        # Should not raise
        release_action_reservation(redis, ORG_ID, OP_ID)


# ---------------------------------------------------------------------------
# BudgetReservation._redis_reserve  (via _redis_reserve directly)
# ---------------------------------------------------------------------------

class TestBudgetReservationRedisReserve:

    def _make_reservation(self, operator, projected_tokens=0, projected_spend_usd=0.0):
        res = BudgetReservation.__new__(BudgetReservation)
        res._client = MagicMock()
        res._settings = MagicMock()
        res._org_id = ORG_ID
        res._operator = operator
        res._operator_id = OP_ID
        res._projected_tokens = max(int(projected_tokens), 0)
        res._projected_spend_usd = max(float(projected_spend_usd), 0.0)
        res.actual_tokens = res._projected_tokens
        res.actual_spend_usd = res._projected_spend_usd
        res._reserved = {}
        res._day = TODAY
        return res

    def test_tokens_within_cap_reserves(self):
        op = _mock_operator(tokens_cap=1000)
        res = self._make_reservation(op, projected_tokens=100)
        redis = MagicMock()
        redis.incrbyfloat.return_value = 100.0

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=1000, spend_cap=None),
        ):
            res._redis = redis
            res._redis_reserve()

        assert res._reserved == {"tokens": 100.0}
        redis.expire.assert_called()

    def test_tokens_over_cap_rolls_back_and_raises(self):
        op = _mock_operator(tokens_cap=500)
        res = self._make_reservation(op, projected_tokens=100)
        redis = MagicMock()
        redis.incrbyfloat.side_effect = [600.0, None]  # over cap, then rollback

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=500, spend_cap=None),
        ):
            res._redis = redis
            with pytest.raises(AutonomousBudgetExceededError) as exc_info:
                res._redis_reserve()

        err = exc_info.value
        assert err.dimension == "tokens"
        assert err.limit == 500.0
        assert err.used == 500.0  # 600 - 100
        assert res._reserved == {}  # rolled back

    def test_spend_over_cap_raises(self):
        op = _mock_operator(spend_cap=10.0)
        res = self._make_reservation(op, projected_spend_usd=1.0)
        redis = MagicMock()
        redis.incrbyfloat.side_effect = [11.5, None]

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=None, spend_cap=10.0),
        ):
            res._redis = redis
            with pytest.raises(AutonomousBudgetExceededError) as exc_info:
                res._redis_reserve()

        assert exc_info.value.dimension == "spend_usd"

    def test_no_caps_no_raise(self):
        op = _mock_operator()  # no caps
        res = self._make_reservation(op, projected_tokens=100, projected_spend_usd=1.0)
        redis = MagicMock()
        redis.incrbyfloat.side_effect = [100.0, 1.0]

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=None, spend_cap=None),
        ):
            res._redis = redis
            res._redis_reserve()  # Should not raise

        assert "tokens" in res._reserved
        assert "spend_usd" in res._reserved

    def test_redis_incr_error_degrades_gracefully(self):
        """When Redis INCR fails mid-reservation, existing increments are rolled back
        and the method returns without raising (degrade, not fail)."""
        op = _mock_operator(tokens_cap=1000)
        res = self._make_reservation(op, projected_tokens=100)
        redis = MagicMock()
        redis.incrbyfloat.side_effect = ConnectionError("timeout")

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=1000, spend_cap=None),
        ):
            res._redis = redis
            res._redis_reserve()  # Should NOT raise

        assert res._reserved == {}  # nothing reserved (degraded)

    def test_both_dims_first_ok_second_fails_rolls_back_first(self):
        """If spend_usd incr succeeds but exceeds cap, the tokens incr must be
        rolled back as well."""
        op = _mock_operator(tokens_cap=1000, spend_cap=5.0)
        res = self._make_reservation(op, projected_tokens=100, projected_spend_usd=1.0)
        redis = MagicMock()
        # tokens incr → 100 (ok), spend incr → 6.0 (over cap 5.0), then 2 rollbacks
        redis.incrbyfloat.side_effect = [100.0, 6.0, None, None]

        with patch(
            "app.services.budget_reservation.get_effective_budgets",
            return_value=_make_budgets(tokens_cap=1000, spend_cap=5.0),
        ):
            res._redis = redis
            with pytest.raises(AutonomousBudgetExceededError) as exc_info:
                res._redis_reserve()

        assert exc_info.value.dimension == "spend_usd"
        assert res._reserved == {}
        # Should have 4 total calls: tokens incr, spend incr, rollback spend, rollback tokens
        assert redis.incrbyfloat.call_count == 4


# ---------------------------------------------------------------------------
# BudgetReservation._redis_reconcile
# ---------------------------------------------------------------------------

class TestBudgetReservationReconcile:

    def _make_reservation_with_reserved(self, reserved: dict[str, float]) -> BudgetReservation:
        res = BudgetReservation.__new__(BudgetReservation)
        res._redis = MagicMock()
        res._reserved = reserved
        res._org_id = ORG_ID
        res._operator_id = OP_ID
        res._day = TODAY
        return res

    def test_actual_equals_reserved_no_adjustment(self):
        res = self._make_reservation_with_reserved({"tokens": 100.0})
        res._redis_reconcile(actual_tokens=100, actual_spend=0.0, failed=False)
        # delta is 0 — no incrbyfloat call
        res._redis.incrbyfloat.assert_not_called()

    def test_actual_less_than_reserved_releases_difference(self):
        res = self._make_reservation_with_reserved({"tokens": 200.0})
        res._redis_reconcile(actual_tokens=150, actual_spend=0.0, failed=False)
        # delta = 150 - 200 = -50
        res._redis.incrbyfloat.assert_called_once()
        args = res._redis.incrbyfloat.call_args.args
        assert abs(args[1] - (-50.0)) < 1e-6

    def test_failed_zeroes_out_reservation(self):
        res = self._make_reservation_with_reserved({"tokens": 200.0, "spend_usd": 2.0})
        res._redis_reconcile(actual_tokens=0, actual_spend=0.0, failed=True)
        # delta for tokens = 0 - 200 = -200; delta for spend = 0 - 2.0 = -2.0
        assert res._redis.incrbyfloat.call_count == 2

    def test_redis_error_in_reconcile_suppressed(self):
        res = self._make_reservation_with_reserved({"tokens": 100.0})
        res._redis.incrbyfloat.side_effect = ConnectionError("down")
        # Should not raise
        res._redis_reconcile(actual_tokens=50, actual_spend=0.0, failed=False)


# ---------------------------------------------------------------------------
# BudgetReservation fallback path (Redis unavailable)
# ---------------------------------------------------------------------------

class TestBudgetReservationFallback:

    @pytest.mark.asyncio
    async def test_falls_back_to_check_when_redis_unavailable(self):
        op = _mock_operator(tokens_cap=1000)
        client = MagicMock()
        settings = MagicMock()

        with patch("app.services.budget_reservation._get_redis", return_value=None), \
             patch("app.services.budget_reservation.check_autonomous_budget") as mock_check, \
             patch("app.services.budget_reservation.record_autonomous_usage") as mock_record:

            async with BudgetReservation(
                client, settings, ORG_ID, op,
                projected_tokens=100, projected_spend_usd=0.5,
            ) as r:
                r.actual_tokens = 80
                r.actual_spend_usd = 0.4

            mock_check.assert_called_once()
            mock_record.assert_called_once_with(
                client, ORG_ID, OP_ID,
                tokens=80, spend_usd=0.4,
            )

    @pytest.mark.asyncio
    async def test_fallback_check_raises_propagated(self):
        op = _mock_operator(tokens_cap=1000)
        client = MagicMock()
        settings = MagicMock()

        with patch("app.services.budget_reservation._get_redis", return_value=None), \
             patch(
                 "app.services.budget_reservation.check_autonomous_budget",
                 side_effect=AutonomousBudgetExceededError(
                     dimension="tokens", limit=1000.0, used=950.0, operator_id=OP_ID
                 ),
             ):
            with pytest.raises(AutonomousBudgetExceededError):
                async with BudgetReservation(
                    client, settings, ORG_ID, op, projected_tokens=100
                ):
                    pass  # should not reach here


# ---------------------------------------------------------------------------
# BudgetReservation happy-path end-to-end (Redis available)
# ---------------------------------------------------------------------------

class TestBudgetReservationHappyPath:

    @pytest.mark.asyncio
    async def test_reserves_then_records_actual(self):
        op = _mock_operator(tokens_cap=5000, spend_cap=10.0)
        client = MagicMock()
        settings = MagicMock()
        mock_redis = MagicMock()
        mock_redis.incrbyfloat.side_effect = [
            300.0,   # tokens reserve → 300
            0.50,    # spend reserve → 0.50
            # reconcile: actual=250/0.40 → delta=-50 and -0.10
            None, None,
        ]

        with patch("app.services.budget_reservation._get_redis", return_value=mock_redis), \
             patch(
                 "app.services.budget_reservation.get_effective_budgets",
                 return_value=_make_budgets(tokens_cap=5000, spend_cap=10.0),
             ), \
             patch("app.services.budget_reservation.record_autonomous_usage") as mock_record:

            async with BudgetReservation(
                client, settings, ORG_ID, op,
                projected_tokens=300, projected_spend_usd=0.50,
            ) as r:
                r.actual_tokens = 250
                r.actual_spend_usd = 0.40

        mock_record.assert_called_once_with(
            client, ORG_ID, OP_ID,
            tokens=250, spend_usd=0.40,
        )

    @pytest.mark.asyncio
    async def test_on_provider_failure_releases_and_skips_record(self):
        op = _mock_operator(tokens_cap=5000)
        client = MagicMock()
        settings = MagicMock()
        mock_redis = MagicMock()
        mock_redis.incrbyfloat.side_effect = [300.0, None]  # reserve, then rollback

        with patch("app.services.budget_reservation._get_redis", return_value=mock_redis), \
             patch(
                 "app.services.budget_reservation.get_effective_budgets",
                 return_value=_make_budgets(tokens_cap=5000, spend_cap=None),
             ), \
             patch("app.services.budget_reservation.record_autonomous_usage") as mock_record:

            with pytest.raises(RuntimeError):
                async with BudgetReservation(
                    client, settings, ORG_ID, op, projected_tokens=300
                ) as r:
                    raise RuntimeError("provider failed")

        # On failure actual=0 → delta=-300 → rollback call
        assert mock_redis.incrbyfloat.call_count >= 2
        # Record should NOT have been called (failed=True)
        mock_record.assert_not_called()
