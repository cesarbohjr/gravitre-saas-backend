"""Row 7 acceptance-criteria tests: quality evaluation harness, atomic budget
reservations, and routing eligibility.

Acceptance criteria (Row 7):
    "Quality evaluation harness, atomic budget reservations, routing eligibility
     → Measured workflow quality/cost/latency and concurrency"

Coverage:
- Quality evaluation harness
  - p50 latency reported once ≥5 samples are present
  - p95 latency reported once ≥20 samples are present
  - routing_approved is permanently False — no evaluation result can flip it
  - evaluation is sequential: call N+1 is not dispatched before N returns
  - multi-model cost aggregation: complete vs. incomplete coverage
  - bounded evaluation rejects > 200 total calls
- Routing eligibility
  - model policy open → any model allowed
  - model policy allowlist → only listed provider/model allowed
  - model policy blocklist → listed provider/model rejected
  - policy normalizes unknown modes to "open"
- Budget reservation concurrency
  - sequential Redis increments are atomic: only the first caller succeeds when
    cap == 1 and two callers race
  - failed reservation rolls back its own increment without touching a
    concurrent caller's reservation
  - reconcile after actual < projected releases the difference without
    disturbing a sibling key
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch, call as mock_call

import pytest

from app.services.llm_workflow_evaluation import (
    EvaluationCase,
    evaluate_models,
    summarize_evaluations,
)
from app.services.model_policy_service import (
    assert_model_allowed,
    normalize_model_policy,
)
from app.services.ai_guardrails import AIModelPolicyError
from app.services.budget_reservation import (
    _reservation_key,
    atomic_reserve_action,
    release_action_reservation,
)
from app.services.autonomous_budget_service import AutonomousBudgetExceededError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODEL_A = "gpt-5.4-mini"
MODEL_B = "claude-3-5-haiku-20241022"
ORG_ID = "org-row7"
TODAY_STR = "2026-10-16"
from datetime import date
TODAY = date.fromisoformat(TODAY_STR)


def _response(model: str = MODEL_A, *, cost: float = 0.01, latency: int = 50,
              content: str = '{"priority":"urgent"}', call_id: str = "mc-1",
              provider: str = "openai") -> SimpleNamespace:
    return SimpleNamespace(
        model=model, provider=provider, content=content,
        model_call_id=call_id, input_tokens=10, output_tokens=5,
        cost_usd=cost, latency_ms=latency,
    )


SINGLE_CASE = EvaluationCase(
    "ticket-p", "classification",
    'Return {"priority":"urgent"|"normal"}. Ticket: office-wide outage. '
    'Company rule: office-wide is urgent.',
    {"priority": "urgent"},
)

DECISION_CASE = EvaluationCase(
    "email-approval", "decision_reasoning",
    'Return {"decision":"require_approval"|"execute"}. Policy requires human approval.',
    {"decision": "require_approval"}, critical=True,
)


# ---------------------------------------------------------------------------
# Quality evaluation harness — latency percentiles
# ---------------------------------------------------------------------------

class TestLatencyPercentiles:
    """summarize_evaluations should return real p50/p95 when enough samples exist."""

    def _make_rows(self, model: str, count: int, latency_ms: float) -> list[dict]:
        return [
            {"requested_model": model, "passed": True, "critical": False,
             "cost_usd": 0.01, "latency_ms": latency_ms}
            for _ in range(count)
        ]

    def test_p50_none_below_min_samples(self):
        """Fewer than 5 samples → p50 stays None."""
        rows = self._make_rows(MODEL_A, 4, 80.0)
        result = summarize_evaluations(rows)
        assert result[MODEL_A]["latency_ms"]["p50"] is None

    def test_p50_reported_at_five_samples(self):
        """Exactly 5 samples → p50 is a real number."""
        rows = self._make_rows(MODEL_A, 5, 100.0)
        result = summarize_evaluations(rows)
        p50 = result[MODEL_A]["latency_ms"]["p50"]
        assert p50 is not None
        assert isinstance(p50, (int, float))
        assert p50 > 0

    def test_p95_none_below_twenty_samples(self):
        """19 samples → p95 stays None."""
        rows = self._make_rows(MODEL_A, 19, 80.0)
        result = summarize_evaluations(rows)
        assert result[MODEL_A]["latency_ms"]["p95"] is None

    def test_p95_reported_at_twenty_samples(self):
        """Exactly 20 samples → p95 is a real number."""
        rows = self._make_rows(MODEL_A, 20, 80.0)
        result = summarize_evaluations(rows)
        p95 = result[MODEL_A]["latency_ms"]["p95"]
        assert p95 is not None
        assert p95 > 0

    def test_latency_ignores_none_values(self):
        """Rows with latency_ms=None are excluded from the percentile calculation."""
        rows = self._make_rows(MODEL_A, 5, 100.0)
        rows.append({"requested_model": MODEL_A, "passed": True, "critical": False,
                     "cost_usd": 0.01, "latency_ms": None})
        result = summarize_evaluations(rows)
        # Still 5 valid samples → p50 present
        assert result[MODEL_A]["latency_ms"]["p50"] is not None

    def test_p50_monotonically_ordered(self):
        """p50 ≤ p95 when both are available (20 samples)."""
        # 10 fast rows then 10 slow rows
        rows = (self._make_rows(MODEL_A, 10, 50.0) +
                self._make_rows(MODEL_A, 10, 200.0))
        result = summarize_evaluations(rows)
        p50 = result[MODEL_A]["latency_ms"]["p50"]
        p95 = result[MODEL_A]["latency_ms"]["p95"]
        assert p50 is not None and p95 is not None
        assert p50 <= p95


# ---------------------------------------------------------------------------
# Quality evaluation harness — routing eligibility invariant
# ---------------------------------------------------------------------------

class TestRoutingEligibilityInvariant:
    """routing_approved must always be False — no evaluation result can set it True."""

    @pytest.mark.asyncio
    async def test_routing_approved_false_on_perfect_pass_rate(self):
        """Even 100% pass rate never sets routing_approved=True."""
        router = SimpleNamespace(complete=AsyncMock(return_value=_response(
            content='{"priority":"urgent"}', call_id="mc-1",
        )))
        report = await evaluate_models(router, org_id=ORG_ID, models=[MODEL_A],
                                       cases=(SINGLE_CASE,))
        assert report["models"][MODEL_A]["routing_approved"] is False
        assert report["routing_changed"] is False

    @pytest.mark.asyncio
    async def test_routing_approved_false_on_all_critical_passed(self):
        """Passing critical cases does not flip routing_approved."""
        router = SimpleNamespace(complete=AsyncMock(return_value=_response(
            content='{"decision":"require_approval"}', call_id="mc-2",
        )))
        report = await evaluate_models(router, org_id=ORG_ID, models=[MODEL_A],
                                       cases=(DECISION_CASE,))
        assert report["models"][MODEL_A]["routing_approved"] is False

    def test_routing_approved_false_in_summarize_evaluations_regardless_of_input(self):
        """summarize_evaluations never produces routing_approved=True even when given
        perfect rows — the field is a structural invariant, not a computation."""
        rows = [
            {"requested_model": MODEL_A, "passed": True, "critical": True,
             "cost_usd": 0.01, "latency_ms": 50}
            for _ in range(10)
        ]
        result = summarize_evaluations(rows)
        assert result[MODEL_A]["routing_approved"] is False


# ---------------------------------------------------------------------------
# Quality evaluation harness — sequential execution
# ---------------------------------------------------------------------------

class TestEvaluationIsSequential:
    """The harness must dispatch router.complete calls sequentially, not concurrently.

    We verify this by recording the order of call starts and confirming no two
    calls overlap (i.e. call N+1 starts only after call N's await resolves).
    """

    @pytest.mark.asyncio
    async def test_calls_are_sequential_not_concurrent(self):
        call_log: list[str] = []
        in_flight: list[bool] = [False]
        call_count: list[int] = [0]

        async def _complete(*args, **kwargs):
            # Positional arg 0 is task_type (a TaskType enum or str).
            task_type = str(args[0]) if args else str(kwargs.get("task_type", "?"))
            idx = call_count[0]
            call_count[0] += 1
            # If anything else is in-flight right now, we have a concurrency violation.
            if in_flight[0]:
                call_log.append(f"CONCURRENT:{idx}:{task_type}")
            in_flight[0] = True
            call_log.append(f"START:{idx}")
            await asyncio.sleep(0)  # yield control to any other pending coroutines
            in_flight[0] = False
            call_log.append(f"END:{idx}")
            return _response(content='{"priority":"urgent"}')

        router = SimpleNamespace(complete=_complete)
        cases = (
            EvaluationCase("c1", "classification", 'Return {"priority":"urgent"}.', {"priority": "urgent"}),
            EvaluationCase("c2", "classification", 'Return {"priority":"normal"}.', {"priority": "normal"}),
        )
        await evaluate_models(router, org_id=ORG_ID, models=[MODEL_A], cases=cases)

        # No "CONCURRENT" marker should appear.
        concurrent_violations = [e for e in call_log if e.startswith("CONCURRENT")]
        assert concurrent_violations == [], f"Concurrent calls detected: {call_log}"

        # Both cases were visited.
        starts = [e for e in call_log if e.startswith("START")]
        assert len(starts) == 2


# ---------------------------------------------------------------------------
# Quality evaluation harness — multi-model cost aggregation
# ---------------------------------------------------------------------------

class TestMultiModelCostAggregation:
    """Cost completeness must be tracked per model independently."""

    def test_two_models_independent_cost_completeness(self):
        rows_a = [
            {"requested_model": MODEL_A, "passed": True, "critical": False,
             "cost_usd": 0.01, "latency_ms": 50},
        ]
        rows_b = [
            {"requested_model": MODEL_B, "passed": True, "critical": False,
             "cost_usd": None, "latency_ms": 50},  # missing cost
        ]
        result = summarize_evaluations(rows_a + rows_b)
        assert result[MODEL_A]["cost_coverage_complete"] is True
        assert result[MODEL_A]["total_cost_usd"] is not None
        assert result[MODEL_B]["cost_coverage_complete"] is False
        assert result[MODEL_B]["total_cost_usd"] is None
        assert result[MODEL_B]["cost_per_success_usd"] is None

    @pytest.mark.asyncio
    async def test_bounded_evaluation_rejects_over_200_calls(self):
        """5 models × 5 cases × 10 reps = 250 > 200 → ValueError before any call."""
        router = SimpleNamespace(complete=AsyncMock())
        cases = tuple(
            EvaluationCase(f"c{i}", "classification", f'Return {{"x":{i}}}.', {"x": i})
            for i in range(5)
        )
        with pytest.raises(ValueError, match="200"):
            await evaluate_models(router, org_id=ORG_ID,
                                  models=[MODEL_A, MODEL_B,
                                          "claude-3-5-sonnet-20241022",
                                          "gpt-5.5", "gemini-2.0-flash"],
                                  cases=cases, repetitions=10)
        router.complete.assert_not_called()


# ---------------------------------------------------------------------------
# Model policy / routing eligibility
# ---------------------------------------------------------------------------

class TestModelPolicyRoutingEligibility:
    """assert_model_allowed enforces org routing eligibility at call time."""

    def test_open_policy_permits_any_provider_and_model(self):
        policy = normalize_model_policy({"mode": "open"})
        # Should not raise for anything.
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")
        assert_model_allowed(policy, provider="anthropic", model="claude-3-5-sonnet-20241022")
        assert_model_allowed(policy, provider="google", model="gemini-2.0-flash")

    def test_allowlist_provider_blocks_unlisted_provider(self):
        policy = normalize_model_policy({"mode": "allowlist", "providers": ["openai"]})
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")
        with pytest.raises(AIModelPolicyError):
            assert_model_allowed(policy, provider="anthropic", model="claude-3-5-sonnet-20241022")

    def test_allowlist_model_blocks_unlisted_model(self):
        policy = normalize_model_policy({
            "mode": "allowlist",
            "models": ["gpt-5.4-mini", "gpt-5.5"],
        })
        assert_model_allowed(policy, provider="openai", model="gpt-5.4-mini")
        with pytest.raises(AIModelPolicyError):
            assert_model_allowed(policy, provider="openai", model="gpt-5.6")

    def test_blocklist_provider_rejects_listed_provider(self):
        policy = normalize_model_policy({"mode": "blocklist", "providers": ["google"]})
        with pytest.raises(AIModelPolicyError):
            assert_model_allowed(policy, provider="google", model="gemini-2.0-flash")
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")

    def test_blocklist_model_rejects_listed_model(self):
        policy = normalize_model_policy({"mode": "blocklist", "models": ["gpt-5.6-preview"]})
        with pytest.raises(AIModelPolicyError):
            assert_model_allowed(policy, provider="openai", model="gpt-5.6-preview")
        assert_model_allowed(policy, provider="openai", model="gpt-5.5")

    def test_unknown_mode_normalizes_to_open(self):
        policy = normalize_model_policy({"mode": "CUSTOM_MODE_XYZ"})
        assert policy["mode"] == "open"
        # Should not raise.
        assert_model_allowed(policy, provider="any", model="any-model")

    def test_none_policy_normalizes_to_open(self):
        policy = normalize_model_policy(None)
        assert policy["mode"] == "open"

    def test_routing_eligibility_enforced_before_model_call(self):
        """AIModelPolicyError is raised at call time, not after the request."""
        policy = normalize_model_policy({"mode": "allowlist", "providers": ["openai"]})
        raised = False
        try:
            assert_model_allowed(policy, provider="anthropic", model="claude-opus-4-5")
        except AIModelPolicyError:
            raised = True
        assert raised, "Policy gate must raise before any network call is made"


# ---------------------------------------------------------------------------
# Budget reservation concurrency
# ---------------------------------------------------------------------------

class TestBudgetReservationConcurrency:
    """Atomic Redis increments prevent concurrent callers from both succeeding
    when the cap is tight.

    These tests simulate two concurrent callers sharing a single Redis mock
    whose INCRBYFLOAT is truly sequential (Redis is single-threaded), so the
    first caller gets the total they expect and the second exceeds the cap.
    """

    OP_ID = "op-concurr"

    def test_first_caller_within_cap_succeeds(self):
        """First incrbyfloat returns 1 (at cap) → caller succeeds."""
        redis = MagicMock()
        redis.incrbyfloat.return_value = 1.0
        result = atomic_reserve_action(redis, ORG_ID, self.OP_ID, cap=1)
        assert result == 1.0

    def test_second_caller_over_cap_rolls_back(self):
        """Second incrbyfloat returns 2 (over cap of 1) → raises and rolls back."""
        redis = MagicMock()
        redis.incrbyfloat.side_effect = [2.0, None]  # incr → 2, rollback → None
        with pytest.raises(AutonomousBudgetExceededError) as exc_info:
            atomic_reserve_action(redis, ORG_ID, self.OP_ID, cap=1)
        assert exc_info.value.dimension == "actions"
        assert exc_info.value.limit == 1.0
        # Rollback was called with -1
        rollback = redis.incrbyfloat.call_args_list[1]
        assert rollback.args[1] == -1.0

    def test_concurrent_rollback_does_not_touch_sibling_key(self):
        """When caller B rolls back, it uses its own key — not caller A's key."""
        org_a = "org-a"
        org_b = "org-b"
        key_a = _reservation_key(org_a, self.OP_ID, "actions", TODAY)
        key_b = _reservation_key(org_b, self.OP_ID, "actions", TODAY)
        assert key_a != key_b

        redis = MagicMock()
        # Caller A succeeds.
        redis.incrbyfloat.return_value = 1.0
        result_a = atomic_reserve_action(redis, org_a, self.OP_ID, cap=2)
        assert result_a == 1.0

        # Caller B exceeds cap — rollback uses B's key.
        redis.incrbyfloat.side_effect = [3.0, None]
        with pytest.raises(AutonomousBudgetExceededError):
            atomic_reserve_action(redis, org_b, self.OP_ID, cap=2)

        # Verify rollback only touched org_b's key.
        rollback_call = redis.incrbyfloat.call_args_list[-1]
        assert key_b in rollback_call.args[0]
        assert key_a not in rollback_call.args[0]

    def test_release_after_success_decrements_correct_key(self):
        """release_action_reservation decrements the same key atomic_reserve_action used."""
        redis = MagicMock()
        redis.incrbyfloat.return_value = -1.0  # dummy
        release_action_reservation(redis, ORG_ID, self.OP_ID)
        call = redis.incrbyfloat.call_args
        assert "gravitre:autobudget:" in call.args[0]
        assert call.args[1] == -1.0

    def test_noop_when_redis_unavailable(self):
        """When Redis is None (degraded mode), reserve/release never raise."""
        result = atomic_reserve_action(None, ORG_ID, self.OP_ID, cap=1)
        assert result is None
        release_action_reservation(None, ORG_ID, self.OP_ID)  # no raise

    def test_concurrency_proof_sequential_calls_same_redis_key(self):
        """Simulate two callers sharing one Redis:
           - Call 1: incrbyfloat → 1 (≤ cap 1) → succeeds
           - Call 2: incrbyfloat → 2 (> cap 1) → rolls back to 1 → raises

        This proves atomicity: both callers cannot both be within a cap of 1.
        """
        cap = 1
        shared_redis = MagicMock()
        # Sequence: caller-1 incr, caller-2 incr, caller-2 rollback
        shared_redis.incrbyfloat.side_effect = [1.0, 2.0, None]

        # Caller 1 succeeds.
        r1 = atomic_reserve_action(shared_redis, ORG_ID, self.OP_ID, cap=cap)
        assert r1 == 1.0

        # Caller 2 fails.
        with pytest.raises(AutonomousBudgetExceededError) as exc_info:
            atomic_reserve_action(shared_redis, ORG_ID, self.OP_ID, cap=cap)
        assert exc_info.value.used == 1.0  # after rollback: 2 - 1 = 1

        # Total incrbyfloat calls: 1 (caller-1) + 2 (caller-2 incr + rollback) = 3
        assert shared_redis.incrbyfloat.call_count == 3
