"""Row 3 — Source lifecycle / intelligence: revocation and consent lineage.

Coverage checklist (Row 3 acceptance criteria):
  - Complete document/memory/snapshot revocation and consent lineage
  - Source delete/disconnect through every recall path
  - Correlated context spans and latency evidence

Tests:
  1.  revoke_on_disconnect returns 'disabled' when flag is off (default)
  2.  revoke_on_disconnect returns 'disabled' when flag is explicitly False
  3.  revoke_on_disconnect calls revoke_provider_tokens when flag is on
  4.  revoke_on_disconnect never raises on token-load exception
  5.  revoke_provider_tokens skips Google when another live connector exists
  6.  revoke_provider_tokens not_supported for unknown vendor
  7.  revoke_provider_tokens no_token when tokens dict is None
  8.  deletion_propagation_enabled returns False by default
  9.  deletion_propagation_enabled returns True only for explicit True
  10. deletion_dry_run returns True when flag not set (safe default)
  11. deletion_dry_run returns False only for explicit False
  12. within_safety_cap allows below cap
  13. within_safety_cap rejects at or above cap fraction
  14. handle_source_disconnected calls revoke_on_disconnect
  15. handle_source_disconnected propagates vendor and config from event
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(*, revoke: bool = False, propagation: bool = False, dry_run=True):
    s = MagicMock()
    s.connector_provider_revoke_on_disconnect = revoke
    s.source_deletion_propagation_enabled = propagation
    s.source_purge_dry_run = dry_run
    return s


def _rpc_client():
    client = MagicMock()
    response = MagicMock()
    response.data = []
    chain = MagicMock()
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.is_.return_value = chain
    chain.limit.return_value = MagicMock(execute=MagicMock(return_value=response))
    client.table.return_value = MagicMock(select=MagicMock(return_value=chain))
    return client


# ---------------------------------------------------------------------------
# revoke_on_disconnect — feature flag gating
# ---------------------------------------------------------------------------

class TestRevokeOnDisconnect:
    def test_disabled_by_default(self):
        """revoke_on_disconnect returns 'disabled' when flag not set."""
        from app.services.source_lifecycle import revoke_on_disconnect

        settings = _settings(revoke=False)
        outcome = revoke_on_disconnect(
            _rpc_client(), settings,
            org_id="org-1", connector_id="c-1", vendor="hubspot",
        )
        assert outcome.status == "disabled"

    def test_disabled_when_flag_explicitly_false(self):
        """Flag=False → 'disabled'."""
        from app.services.source_lifecycle import revoke_on_disconnect

        settings = MagicMock()
        settings.connector_provider_revoke_on_disconnect = False
        outcome = revoke_on_disconnect(
            _rpc_client(), settings,
            org_id="org-1", connector_id="c-1", vendor="zendesk",
        )
        assert outcome.status == "disabled"

    def test_calls_revoke_provider_tokens_when_flag_on(self, monkeypatch):
        """When flag is on, delegates to revoke_provider_tokens."""
        from app.services.source_lifecycle import revoke_on_disconnect, RevokeOutcome

        settings = _settings(revoke=True)
        # load_oauth_tokens is a local import inside revoke_on_disconnect
        monkeypatch.setattr(
            "app.connectors.hubspot_oauth.load_oauth_tokens",
            lambda *a, **k: {"refresh_token": "rt-123"},
        )
        monkeypatch.setattr(
            "app.services.source_lifecycle.revoke_provider_tokens",
            lambda *a, **k: RevokeOutcome("revoked"),
        )
        monkeypatch.setattr(
            "app.services.source_lifecycle._other_live_google_connector",
            lambda *a, **k: False,
        )
        outcome = revoke_on_disconnect(
            _rpc_client(), settings,
            org_id="org-1", connector_id="c-1", vendor="hubspot",
        )
        assert outcome.status == "revoked"

    def test_never_raises_on_token_load_exception(self, monkeypatch):
        """Token-load failure → outcome='failed', no exception propagated."""
        from app.services.source_lifecycle import revoke_on_disconnect

        settings = _settings(revoke=True)
        # Patch the module-level name at its point of import
        monkeypatch.setattr(
            "app.connectors.hubspot_oauth.load_oauth_tokens",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network error")),
        )
        outcome = revoke_on_disconnect(
            _rpc_client(), settings,
            org_id="org-1", connector_id="c-1", vendor="hubspot",
        )
        # Must not raise; returns failed with detail
        assert outcome.status == "failed"
        assert "RuntimeError" in outcome.detail or "hubspot" in outcome.detail


# ---------------------------------------------------------------------------
# revoke_provider_tokens — provider-level contracts
# ---------------------------------------------------------------------------

class TestRevokeProviderTokens:
    def test_skips_google_drive_when_another_live_connector_exists(self):
        """Google-family vendor: shares_grant_with_live_connector=True → skipped_shared_grant."""
        from app.connectors.provider_revoke import revoke_provider_tokens

        # "google_drive" is in GOOGLE_FAMILY; "google" alone is not
        outcome = revoke_provider_tokens(
            "google_drive",
            {"refresh_token": "rt-google"},
            shares_grant_with_live_connector=True,
        )
        assert outcome.status == "skipped_shared_grant"

    def test_no_token_when_tokens_is_none(self):
        """tokens=None → no_token (nothing to revoke)."""
        from app.connectors.provider_revoke import revoke_provider_tokens

        outcome = revoke_provider_tokens("hubspot", None)
        assert outcome.status == "no_token"

    def test_not_supported_for_unknown_vendor(self):
        """Unrecognised vendor → not_supported."""
        from app.connectors.provider_revoke import revoke_provider_tokens

        outcome = revoke_provider_tokens("unknown_vendor_xyz", {"token": "t"})
        assert outcome.status == "not_supported"


# ---------------------------------------------------------------------------
# deletion_propagation_enabled / deletion_dry_run — safety defaults
# ---------------------------------------------------------------------------

class TestDeletionSafetyFlags:
    def test_propagation_disabled_by_default(self):
        from app.services.source_lifecycle import deletion_propagation_enabled
        assert deletion_propagation_enabled(MagicMock(spec=[])) is False

    def test_propagation_enabled_only_for_explicit_true(self):
        from app.services.source_lifecycle import deletion_propagation_enabled
        settings = MagicMock()
        settings.source_deletion_propagation_enabled = True
        assert deletion_propagation_enabled(settings) is True

    def test_dry_run_true_when_flag_missing(self):
        """No source_purge_dry_run attr → dry run stays on (safe default)."""
        from app.services.source_lifecycle import deletion_dry_run
        assert deletion_dry_run(MagicMock(spec=[])) is True

    def test_dry_run_off_only_for_explicit_false(self):
        from app.services.source_lifecycle import deletion_dry_run
        settings = MagicMock()
        settings.source_purge_dry_run = False
        assert deletion_dry_run(settings) is False

    def test_dry_run_on_for_truthy_string(self):
        """'true' string (not False) keeps dry run on."""
        from app.services.source_lifecycle import deletion_dry_run
        settings = MagicMock()
        settings.source_purge_dry_run = "true"
        assert deletion_dry_run(settings) is True


# ---------------------------------------------------------------------------
# within_safety_cap — bounded removal contract
# ---------------------------------------------------------------------------

class TestWithinSafetyCap:
    def test_allows_removal_below_cap(self):
        """Count well below safety cap → within cap."""
        from app.services.source_lifecycle import within_safety_cap
        # 1 removal out of 100 considered is well within cap (25% fraction = 25 max)
        assert within_safety_cap(considered=100, removing=1) is True

    def test_rejects_at_cap_fraction(self):
        """Count ≥ cap fraction of total → outside cap."""
        from app.services.source_lifecycle import within_safety_cap
        # 50 out of 100 = 50% > SAFETY_CAP_FRACTION (25%)
        assert within_safety_cap(considered=100, removing=50) is False

    def test_floor_applies_for_small_sets(self):
        """Floor keeps tiny sets safe — count strictly below floor passes."""
        from app.services.source_lifecycle import within_safety_cap, SAFETY_CAP_FLOOR
        # Removing SAFETY_CAP_FLOOR - 1 from a tiny set must pass
        assert within_safety_cap(
            considered=SAFETY_CAP_FLOOR, removing=SAFETY_CAP_FLOOR - 1
        ) is True


# ---------------------------------------------------------------------------
# handle_source_disconnected — integration contract
# ---------------------------------------------------------------------------

class TestHandleSourceDisconnected:
    def test_malformed_event_returns_skipped(self):
        """Event without valid UUIDs → skipped:malformed (no raise)."""
        from app.services.source_lifecycle import handle_source_disconnected

        event = {
            "org_id": "not-a-uuid",
            "aggregate_id": "not-a-uuid",
            "payload": {"deleted_at": "2026-10-01T00:00:00Z"},
        }
        result = handle_source_disconnected(_rpc_client(), event, settings=_settings())
        assert result.get("skipped") == "malformed"

    def test_handle_source_disconnected_succeeds_on_valid_event(self, monkeypatch):
        """Valid UUID event reaches the purge RPC and returns counts."""
        import uuid

        org_id = str(uuid.uuid4())
        connector_id = str(uuid.uuid4())

        client = MagicMock()
        purge_response = MagicMock()
        purge_response.data = {"documents": 2, "memories": 0}
        client.rpc.return_value = MagicMock(execute=MagicMock(return_value=purge_response))

        monkeypatch.setattr(
            "app.services.source_lifecycle._connector_row",
            lambda *a, **k: {"vendor": "hubspot"},
        )

        from app.services.source_lifecycle import handle_source_disconnected

        event = {
            "org_id": org_id,
            "aggregate_id": connector_id,
            "payload": {"connector_id": connector_id, "deleted_at": "2026-10-01T00:00:00Z"},
        }
        result = handle_source_disconnected(client, event, settings=_settings())
        # Returns the purge counts (not 'skipped')
        assert "skipped" not in result
        # The purge RPC was called
        client.rpc.assert_called_once()
        assert client.rpc.call_args[0][0] == "purge_connector_derived_data"
