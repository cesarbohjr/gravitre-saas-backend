"""Voice latency (2026-09-05): resolve_connector_auth_status must not repeat
blocking, synchronous per-vendor network calls within a short window.

Root-cause evidence: a live consequential voice turn re-checked the SAME
Slack connector 5 times in ~10 seconds (each a real network call), which
alone accounted for most of a ~14s response
(docs/delivery/voice-latency-connector-status-rootcause-2026-09-05.md).
resolve_connector_auth_status is the single dispatch point every vendor
check (Slack, HubSpot, Salesforce, ...) funnels through, so a short shared
TTL cache there benefits every caller uniformly without any spoken_mode
plumbing, and does not reduce real staleness detection meaningfully (OAuth
tokens do not flip validity within seconds).
"""
from __future__ import annotations

from unittest.mock import patch

from app.connectors import connection_health as ch


def setup_function(_fn) -> None:
    # Module-level cache must not leak state between tests.
    ch._auth_status_cache.clear()


def test_repeated_calls_within_ttl_hit_cache_not_the_network():
    """MUTATION PROOF: remove the cache and call count flips from 1 to 5."""
    with patch.object(
        ch, "_resolve_connector_auth_status_uncached", return_value="auth_expired"
    ) as underlying:
        for _ in range(5):
            result = ch.resolve_connector_auth_status(
                client=object(),
                org_id="org-1",
                connector_id="conn-1",
                vendor="slack",
                settings=object(),
                environment_name="production",
            )
            assert result == "auth_expired"

        assert underlying.call_count == 1, (
            "5 calls for the same connector within the TTL window must reach the "
            "network exactly once, not once per call"
        )


def test_different_connectors_are_not_conflated():
    with patch.object(
        ch,
        "_resolve_connector_auth_status_uncached",
        side_effect=["connected", "auth_expired"],
    ) as underlying:
        first = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-1",
            vendor="slack",
            settings=object(),
        )
        second = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-2",
            vendor="slack",
            settings=object(),
        )

        assert first == "connected"
        assert second == "auth_expired"
        assert underlying.call_count == 2


def test_force_refresh_bypasses_the_cache():
    with patch.object(
        ch,
        "_resolve_connector_auth_status_uncached",
        side_effect=["auth_expired", "connected"],
    ) as underlying:
        first = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-1",
            vendor="slack",
            settings=object(),
        )
        second = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-1",
            vendor="slack",
            settings=object(),
            force_refresh=True,
        )

        assert first == "auth_expired"
        assert second == "connected", "force_refresh must reach the network again"
        assert underlying.call_count == 2


def test_cache_expires_after_ttl(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(ch.time, "monotonic", lambda: fake_time[0])

    with patch.object(
        ch,
        "_resolve_connector_auth_status_uncached",
        side_effect=["auth_expired", "connected"],
    ) as underlying:
        first = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-1",
            vendor="slack",
            settings=object(),
        )
        fake_time[0] += ch._AUTH_STATUS_CACHE_TTL_SECONDS + 1
        second = ch.resolve_connector_auth_status(
            client=object(),
            org_id="org-1",
            connector_id="conn-1",
            vendor="slack",
            settings=object(),
        )

        assert first == "auth_expired"
        assert second == "connected", "cache must expire and re-check after the TTL"
        assert underlying.call_count == 2
