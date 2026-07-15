"""AI Visibility UI connector tests — allowlist + LinkedIn hard reject."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.connectors.ai_visibility_ui_api import (
    AiVisibilityUiError,
    mentions_check,
    surfaces_list,
)


def test_surfaces_list_allowlist():
    surfaces = surfaces_list()
    ids = {s["id"] for s in surfaces}
    assert ids == {"chatgpt", "perplexity", "gemini", "copilot", "claude"}
    assert "linkedin" not in ids
    for row in surfaces:
        assert "entry_url" in row and row["entry_url"].startswith("https://")
        assert "linkedin" not in row["entry_url"].lower()


def test_mentions_check_rejects_linkedin_surface():
    settings = MagicMock()
    settings.browser_agent_enabled = True
    settings.browser_agent_interact_enabled = False
    with pytest.raises(AiVisibilityUiError) as exc_info:
        mentions_check(
            brand="Acme",
            prompt="best CRM tools",
            surface="linkedin",
            settings=settings,
        )
    assert exc_info.value.status_code == 403
    assert "linkedin" in str(exc_info.value).lower()


def test_mentions_check_rejects_linkedin_url_alias():
    settings = MagicMock()
    settings.browser_agent_enabled = True
    settings.browser_agent_interact_enabled = False
    with pytest.raises(AiVisibilityUiError) as exc_info:
        mentions_check(
            brand="Acme",
            prompt="best CRM tools",
            surface="https://www.linkedin.com/feed",
            settings=settings,
        )
    assert exc_info.value.status_code == 403
