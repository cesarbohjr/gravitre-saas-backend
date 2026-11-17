"""Bounded regression for canonical LIVE fallthrough reason parsing."""

import pytest

from app.services.unified_turn_fallthrough import (
    assert_known_fallthrough_reason,
    is_known_fallthrough_reason,
)


@pytest.mark.parametrize("reason", ["outcome_", "unhandled_kind_", "", None])
def test_empty_dynamic_reason_is_rejected(reason):
    assert not is_known_fallthrough_reason(reason)
    with pytest.raises(ValueError, match="unknown fallthrough_reason"):
        assert_known_fallthrough_reason(reason)


@pytest.mark.parametrize("reason", ["outcome_error", "outcome_timeout", "unhandled_kind_other", "live_disabled"])
def test_known_reason_remains_accepted(reason):
    assert is_known_fallthrough_reason(reason)
    assert assert_known_fallthrough_reason(reason) == reason
