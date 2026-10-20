"""Settings > Security shows the real SP URLs an admin pastes into their IdP."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers.sso import sso_service_provider


def test_service_provider_urls_follow_public_app_url():
    settings = MagicMock(public_app_url="https://gravitre.app/")
    out = sso_service_provider(MagicMock(), {"user_id": "u"}, "org-1", settings)
    assert out == {
        "metadata_url": "https://gravitre.app/api/auth/sso/metadata",
        "entity_id": "https://gravitre.app/api/auth/sso/metadata",
        "acs_url": "https://gravitre.app/api/auth/sso/callback",
    }


def test_service_provider_needs_an_org():
    with pytest.raises(HTTPException) as exc:
        sso_service_provider(MagicMock(), {"user_id": "u"}, None, MagicMock(public_app_url="https://gravitre.app"))
    assert exc.value.status_code == 403
