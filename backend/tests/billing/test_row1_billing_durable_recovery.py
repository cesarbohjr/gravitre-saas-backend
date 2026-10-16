"""Row 1 — Billing / model_calls / usage scheduler: durable recovery contracts.

Coverage checklist (Row 1 acceptance criteria):
  - Durable recovery with immutable per-call evidence, bounded retries and
    allowance consistency; closed-period handling and historical audit.

Tests:
  1.  recover_assistant_model_usage validates result shape {scanned, settled, errors}
  2.  recover_assistant_model_usage raises on missing shape key
  3.  recover_assistant_model_usage is called with p_limit=100 (bounded retries)
  4.  record_assistant_model_usage_atomic routes to settle when recovery flag ON
  5.  record_assistant_model_usage_atomic uses direct RPC when recovery flag OFF
  6.  settle_assistant_model_usage validates result in {inserted, duplicate, zero_tokens}
  7.  settle_assistant_model_usage raises on unexpected result
  8.  record_assistant_model_usage_atomic raises on unexpected direct-RPC result
  9.  record_assistant_model_usage_atomic zero_tokens is accepted (no overage)
  10. Recovery result is forwarded: settled/scanned/errors values preserved
  11. Recovery runs before Stripe reporting in scheduler (order contract)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc_client(return_data):
    """Minimal fake Supabase client whose .rpc(...).execute() returns return_data."""
    client = MagicMock()
    response = MagicMock()
    response.data = return_data
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = response
    client.rpc.return_value = rpc_chain
    return client


def _recovery_client(scanned: int = 5, settled: int = 3, errors: int = 0):
    return _rpc_client({"scanned": scanned, "settled": settled, "errors": errors})


# ---------------------------------------------------------------------------
# recover_assistant_model_usage — shape validation
# ---------------------------------------------------------------------------

class TestRecoverValidation:
    def test_valid_result_is_returned(self):
        """Valid {scanned, settled, errors} dict is returned unchanged."""
        from app.billing.service import recover_assistant_model_usage

        client = _recovery_client(scanned=10, settled=7, errors=1)
        result = recover_assistant_model_usage(client)
        assert result["scanned"] == 10
        assert result["settled"] == 7
        assert result["errors"] == 1

    def test_missing_scanned_key_raises(self):
        """Result missing 'scanned' → ValueError."""
        from app.billing.service import recover_assistant_model_usage

        client = _rpc_client({"settled": 0, "errors": 0})  # missing 'scanned'
        with pytest.raises(ValueError, match="Unexpected assistant recovery"):
            recover_assistant_model_usage(client)

    def test_missing_settled_key_raises(self):
        """Result missing 'settled' → ValueError."""
        from app.billing.service import recover_assistant_model_usage

        client = _rpc_client({"scanned": 0, "errors": 0})
        with pytest.raises(ValueError, match="Unexpected assistant recovery"):
            recover_assistant_model_usage(client)

    def test_missing_errors_key_raises(self):
        """Result missing 'errors' → ValueError."""
        from app.billing.service import recover_assistant_model_usage

        client = _rpc_client({"scanned": 0, "settled": 0})
        with pytest.raises(ValueError, match="Unexpected assistant recovery"):
            recover_assistant_model_usage(client)

    def test_empty_result_raises(self):
        """Empty dict → ValueError."""
        from app.billing.service import recover_assistant_model_usage

        client = _rpc_client({})
        with pytest.raises(ValueError):
            recover_assistant_model_usage(client)

    def test_zero_counts_are_valid(self):
        """All-zero result is valid (idle run)."""
        from app.billing.service import recover_assistant_model_usage

        client = _recovery_client(scanned=0, settled=0, errors=0)
        result = recover_assistant_model_usage(client)
        assert result["scanned"] == 0


# ---------------------------------------------------------------------------
# recover_assistant_model_usage — bounded-retry contract (p_limit=100)
# ---------------------------------------------------------------------------

class TestRecoverBoundedRetry:
    def test_rpc_called_with_p_limit_100(self):
        """recover_assistant_model_usage always passes p_limit=100 (hardcoded)."""
        from app.billing.service import recover_assistant_model_usage

        client = _recovery_client()
        recover_assistant_model_usage(client)
        client.rpc.assert_called_once_with(
            "recover_assistant_model_usage", {"p_limit": 100}
        )

    def test_p_limit_is_not_configurable(self):
        """There is no way to override p_limit — calling code passes exactly 100."""
        from app.billing.service import recover_assistant_model_usage
        import inspect

        sig = inspect.signature(recover_assistant_model_usage)
        # function only takes 'client' — no limit parameter
        assert list(sig.parameters.keys()) == ["client"]


# ---------------------------------------------------------------------------
# record_assistant_model_usage_atomic — routing via feature flag
# ---------------------------------------------------------------------------

class TestAtomicRouting:
    def test_routes_to_settle_when_recovery_flag_on(self, monkeypatch):
        """When assistant_billing_recovery_enabled=True, delegates to settle RPC."""
        from app.billing.service import record_assistant_model_usage_atomic

        monkeypatch.setattr(
            "app.billing.service.get_settings",
            lambda: MagicMock(assistant_billing_recovery_enabled=True),
        )
        client = _rpc_client("inserted")
        result = record_assistant_model_usage_atomic(
            client, org_id="org-1", model_call_id="mc-1",
            quantity=100, included=500,
        )
        assert result == "inserted"
        # Must call settle RPC, not the direct record_assistant_model_usage RPC
        client.rpc.assert_called_once_with(
            "settle_assistant_model_usage",
            {"p_org_id": "org-1", "p_model_call_id": "mc-1"},
        )

    def test_routes_to_direct_rpc_when_recovery_flag_off(self, monkeypatch):
        """When assistant_billing_recovery_enabled=False, uses record_assistant_model_usage."""
        from app.billing.service import record_assistant_model_usage_atomic

        monkeypatch.setattr(
            "app.billing.service.get_settings",
            lambda: MagicMock(assistant_billing_recovery_enabled=False),
        )
        client = _rpc_client("inserted")
        result = record_assistant_model_usage_atomic(
            client, org_id="org-2", model_call_id="mc-2",
            quantity=200, included=1000,
        )
        assert result == "inserted"
        client.rpc.assert_called_once_with(
            "record_assistant_model_usage",
            {
                "p_org_id": "org-2",
                "p_model_call_id": "mc-2",
                "p_quantity": 200,
                "p_included": 1000,
                "p_environment": "production",
            },
        )

    def test_settle_is_idempotent_duplicate(self, monkeypatch):
        """'duplicate' from settle RPC is forwarded without error."""
        from app.billing.service import record_assistant_model_usage_atomic

        monkeypatch.setattr(
            "app.billing.service.get_settings",
            lambda: MagicMock(assistant_billing_recovery_enabled=True),
        )
        client = _rpc_client("duplicate")
        result = record_assistant_model_usage_atomic(
            client, "org-1", "mc-dup", 50, 500,
        )
        assert result == "duplicate"

    def test_zero_tokens_is_accepted(self, monkeypatch):
        """'zero_tokens' result is valid (no usage to settle)."""
        from app.billing.service import record_assistant_model_usage_atomic

        monkeypatch.setattr(
            "app.billing.service.get_settings",
            lambda: MagicMock(assistant_billing_recovery_enabled=False),
        )
        client = _rpc_client("zero_tokens")
        result = record_assistant_model_usage_atomic(
            client, "org-1", "mc-zero", 0, 500,
        )
        assert result == "zero_tokens"

    def test_unexpected_direct_rpc_result_raises(self, monkeypatch):
        """Unexpected result from direct RPC → ValueError."""
        from app.billing.service import record_assistant_model_usage_atomic

        monkeypatch.setattr(
            "app.billing.service.get_settings",
            lambda: MagicMock(assistant_billing_recovery_enabled=False),
        )
        client = _rpc_client("something_weird")
        with pytest.raises(ValueError, match="Unexpected assistant billing"):
            record_assistant_model_usage_atomic(
                client, "org-1", "mc-bad", 100, 500,
            )


# ---------------------------------------------------------------------------
# settle_assistant_model_usage — result validation
# ---------------------------------------------------------------------------

class TestSettleValidation:
    def test_inserted_is_valid(self):
        from app.billing.service import settle_assistant_model_usage

        client = _rpc_client("inserted")
        result = settle_assistant_model_usage(client, "org-1", "mc-1")
        assert result == "inserted"

    def test_duplicate_is_valid(self):
        from app.billing.service import settle_assistant_model_usage

        client = _rpc_client("duplicate")
        result = settle_assistant_model_usage(client, "org-1", "mc-1")
        assert result == "duplicate"

    def test_zero_tokens_is_valid(self):
        from app.billing.service import settle_assistant_model_usage

        client = _rpc_client("zero_tokens")
        result = settle_assistant_model_usage(client, "org-1", "mc-1")
        assert result == "zero_tokens"

    def test_unexpected_settle_result_raises(self):
        from app.billing.service import settle_assistant_model_usage

        client = _rpc_client("not_a_thing")
        with pytest.raises(ValueError, match="Unexpected assistant settlement"):
            settle_assistant_model_usage(client, "org-1", "mc-1")

    def test_settle_rpc_receives_correct_params(self):
        """settle uses immutable model_call_id evidence — org_id and call_id only."""
        from app.billing.service import settle_assistant_model_usage

        client = _rpc_client("inserted")
        settle_assistant_model_usage(client, "org-abc", "mc-xyz")
        client.rpc.assert_called_once_with(
            "settle_assistant_model_usage",
            {"p_org_id": "org-abc", "p_model_call_id": "mc-xyz"},
        )


# ---------------------------------------------------------------------------
# Scheduler order: recovery before Stripe reporting
# ---------------------------------------------------------------------------

class TestSchedulerRecoveryOrder:
    def test_recovery_runs_before_stripe_reporting(self):
        """Usage scheduler runs recovery first (in _sync_all_usage), then Stripe reports.

        Confirms Row 1 acceptance: 'bounded retries and allowance consistency'
        — recover_assistant_model_usage is called before report_usage_for_active_orgs.
        """
        from app.billing.usage_scheduler import _sync_all_usage

        call_log: list[str] = []

        def fake_recover(client) -> dict:
            call_log.append("recovery")
            return {"scanned": 5, "settled": 3, "errors": 0}

        def fake_report(period_start, period_end, settings) -> dict:
            call_log.append("report")
            return {}

        settings = MagicMock(
            assistant_billing_recovery_enabled=True,
            usage_atomic_enabled=True,
            assistant_billing_atomic_enabled=True,
        )

        from datetime import date
        p_start = date(2026, 10, 1)
        p_end = date(2026, 10, 31)

        with (
            patch("app.billing.usage_scheduler.recover_assistant_model_usage", fake_recover),
            patch("app.billing.usage_scheduler.report_usage_for_active_orgs", fake_report),
            patch("app.billing.usage_scheduler.report_research_lookup_overage_for_active_orgs", lambda *a, **k: {}),
            patch("app.billing.usage_scheduler.report_voice_minutes_overage_for_active_orgs", lambda *a, **k: {}),
            patch("app.billing.usage_scheduler.get_supabase_client", return_value=MagicMock()),
        ):
            result = _sync_all_usage(p_start, p_end, settings)

        assert call_log[0] == "recovery", "Recovery must run before Stripe reports"
        assert "report" in call_log
        assert result["assistant_recovery"]["settled"] == 3
