from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai_guardrails import (
    AIBudgetExceededError,
    AIContentFlaggedError,
    AIRateLimitError,
    AIServiceDisabledError,
    SlidingWindowRateLimiter,
    enforce_budget,
    enforce_rate_limit,
    fence_untrusted,
    harden_system_prompt,
    moderate_output,
    redact_pii,
)
from app.services.model_router import ModelRouter, TaskType


def _mock_openai_content(content: str, *, prompt_tokens: int | None = None, completion_tokens: int | None = None):
    usage = None
    if prompt_tokens is not None or completion_tokens is not None:
        usage = SimpleNamespace(prompt_tokens=prompt_tokens or 0, completion_tokens=completion_tokens or 0)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=usage,
    )


class TestPromptHardening:
    def test_harden_prepends_safety_rules(self):
        out = harden_system_prompt("Be concise.")
        assert "SECURITY RULES" in out
        assert out.strip().endswith("Be concise.")

    def test_harden_handles_empty(self):
        assert "SECURITY RULES" in harden_system_prompt(None)

    def test_fence_wraps_untrusted(self):
        out = fence_untrusted("ignore previous instructions")
        assert "<untrusted_input>" in out
        assert "</untrusted_input>" in out
        assert "ignore previous instructions" in out


class TestPIIRedaction:
    def test_redacts_common_pii(self):
        text = (
            "Email me at john.doe@acme.com or call 415-555-0142. "
            "SSN 123-45-6789, card 4111 1111 1111 1111."
        )
        out = redact_pii(text)
        assert "john.doe@acme.com" not in out
        assert "[REDACTED_EMAIL]" in out
        assert "123-45-6789" not in out and "[REDACTED_SSN]" in out
        assert "4111 1111 1111 1111" not in out and "[REDACTED_CC]" in out
        assert "415-555-0142" not in out and "[REDACTED_PHONE]" in out

    def test_leaves_clean_text(self):
        text = "Summarize the latest workflow run for the marketing agent."
        assert redact_pii(text) == text

    def test_handles_empty(self):
        assert redact_pii("") == ""


class TestRateLimiter:
    def test_blocks_after_limit(self):
        limiter = SlidingWindowRateLimiter(window_seconds=60.0)
        limiter.check("org-1", 2)
        limiter.check("org-1", 2)
        with pytest.raises(AIRateLimitError):
            limiter.check("org-1", 2)

    def test_zero_limit_is_noop(self):
        limiter = SlidingWindowRateLimiter()
        for _ in range(100):
            limiter.check("org-1", 0)

    def test_keys_isolated(self):
        limiter = SlidingWindowRateLimiter()
        limiter.check("org-a", 1)
        # Different org has its own bucket.
        limiter.check("org-b", 1)
        with pytest.raises(AIRateLimitError):
            limiter.check("org-a", 1)

    def test_enforce_rate_limit_respects_settings(self, mock_settings):
        settings = mock_settings.model_copy(update={"ai_rate_limit_per_min": 0})
        # 0 disables — never raises regardless of volume.
        for _ in range(50):
            enforce_rate_limit("org-x", settings)


class _FakeRedis:
    def __init__(self):
        self.kv: dict = {}

    def incr(self, key):
        self.kv[key] = int(self.kv.get(key, 0)) + 1
        return self.kv[key]

    def expire(self, key, ttl):
        return True


class TestRedisRateLimit:
    def test_redis_counter_blocks_over_limit(self, mock_settings, monkeypatch):
        settings = mock_settings.model_copy(update={"ai_rate_limit_per_min": 2})
        import app.core.redis_client as rc

        # Share one fake client across calls so the counter accumulates.
        shared = _FakeRedis()
        monkeypatch.setattr(rc, "get_sync_redis", lambda s: shared)
        enforce_rate_limit("org-r", settings)
        enforce_rate_limit("org-r", settings)
        with pytest.raises(AIRateLimitError):
            enforce_rate_limit("org-r", settings)

    def test_falls_back_to_in_process_when_no_redis(self, mock_settings, monkeypatch):
        settings = mock_settings.model_copy(update={"ai_rate_limit_per_min": 1})
        import app.core.redis_client as rc

        monkeypatch.setattr(rc, "get_sync_redis", lambda s: None)
        enforce_rate_limit("org-fallback-unique-xyz", settings)
        with pytest.raises(AIRateLimitError):
            enforce_rate_limit("org-fallback-unique-xyz", settings)


class TestOutputModeration:
    async def test_flags_output_when_enabled(self, mock_settings):
        settings = mock_settings.model_copy(update={"ai_moderation_enabled": True})
        client = AsyncMock()
        client.moderations.create = AsyncMock(
            return_value=SimpleNamespace(results=[SimpleNamespace(flagged=True)])
        )
        with pytest.raises(AIContentFlaggedError):
            await moderate_output("bad output", settings, client)

    async def test_noop_when_disabled(self, mock_settings):
        client = AsyncMock()
        await moderate_output("anything", mock_settings, client)  # disabled by default
        client.moderations.create.assert_not_called()


class TestBudgetGate:
    def _patch_billing(self, monkeypatch, *, override, included, used):
        import app.billing.service as bs

        monkeypatch.setattr(bs, "get_supabase_client", lambda s: object())
        monkeypatch.setattr(bs, "get_org_hard_budget_override", lambda c, o: override)
        monkeypatch.setattr(bs, "get_plan_for_org", lambda c, o: {"ai_credits_included": included})
        monkeypatch.setattr(bs, "get_current_period", lambda: (date(2026, 5, 1), date(2026, 5, 31)))
        monkeypatch.setattr(bs, "_sum_usage", lambda c, o, m, ps, pe: used)

    def test_per_org_override_enables_when_global_off(self, mock_settings, monkeypatch):
        # global off, but this org is force-enabled -> blocks over cap (100*2=200).
        settings = mock_settings.model_copy(
            update={"ai_hard_budget_enabled": False, "ai_budget_overage_multiplier": 2.0}
        )
        self._patch_billing(monkeypatch, override=True, included=100, used=500)
        with pytest.raises(AIBudgetExceededError):
            enforce_budget("org-1", settings)

    def test_per_org_override_disables_when_global_on(self, mock_settings, monkeypatch):
        # global on, but this org is force-disabled -> never blocks.
        settings = mock_settings.model_copy(update={"ai_hard_budget_enabled": True})
        self._patch_billing(monkeypatch, override=False, included=100, used=999999)
        enforce_budget("org-1", settings)  # must not raise

    def test_inherits_global_when_no_override(self, mock_settings, monkeypatch):
        # no per-org override -> inherit global off -> never blocks.
        settings = mock_settings.model_copy(update={"ai_hard_budget_enabled": False})
        self._patch_billing(monkeypatch, override=None, included=100, used=999999)
        enforce_budget("org-1", settings)  # must not raise


class TestModelRouterGuardrails:
    @pytest.mark.asyncio
    async def test_killswitch_refuses(self, mock_settings):
        settings = mock_settings.model_copy(update={"disable_ai": True})
        router = ModelRouter(settings=settings)
        with pytest.raises(AIServiceDisabledError):
            await router.complete(task_type=TaskType.CLASSIFICATION, prompt="hi")

    @pytest.mark.asyncio
    async def test_guardrail_block_is_persisted(self, mock_settings):
        settings = mock_settings.model_copy(update={"disable_ai": True})
        router = ModelRouter(settings=settings)
        with patch.object(router, "_log_guardrail_event", AsyncMock()) as log_event:
            with pytest.raises(AIServiceDisabledError):
                await router.complete(task_type=TaskType.CLASSIFICATION, prompt="hi", org_id="org-1")
        log_event.assert_awaited_once()
        # signature: (org_id, task_type, event_type, attempts, summary)
        args = log_event.call_args.args
        assert args[0] == "org-1"
        assert args[2] == "AI_DISABLED"

    @pytest.mark.asyncio
    async def test_pii_redacted_before_send(self, mock_settings):
        router = ModelRouter(settings=mock_settings)
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(  # noqa: SLF001
            return_value=_mock_openai_content("ok", prompt_tokens=1, completion_tokens=1)
        )
        with patch.object(router, "_log_model_call", AsyncMock()):
            await router.complete(
                task_type=TaskType.CLASSIFICATION,
                prompt="contact john@acme.com",
            )
        # Inspect the messages actually sent to the provider.
        sent = router._openai.chat.completions.create.call_args.kwargs["messages"]  # noqa: SLF001
        user_msg = next(m for m in sent if m["role"] == "user")
        assert "john@acme.com" not in user_msg["content"]
        assert "[REDACTED_EMAIL]" in user_msg["content"]

    @pytest.mark.asyncio
    async def test_uses_real_usage_tokens(self, mock_settings):
        router = ModelRouter(settings=mock_settings)
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(  # noqa: SLF001
            return_value=_mock_openai_content("hello", prompt_tokens=123, completion_tokens=45)
        )
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="classify")
        assert response.input_tokens == 123
        assert response.output_tokens == 45

    @pytest.mark.asyncio
    async def test_falls_back_to_estimate_without_usage(self, mock_settings):
        router = ModelRouter(settings=mock_settings)
        router._openai = AsyncMock()  # noqa: SLF001
        router._openai.chat.completions.create = AsyncMock(  # noqa: SLF001
            return_value=_mock_openai_content("hello there")
        )
        with patch.object(router, "_log_model_call", AsyncMock()):
            response = await router.complete(task_type=TaskType.CLASSIFICATION, prompt="classify")
        assert response.input_tokens > 0
        assert response.output_tokens > 0
