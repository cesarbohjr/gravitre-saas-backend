"""Regression: Dictate /api/voice/stt must not UnboundLocalError on get_supabase_client."""
from __future__ import annotations

import inspect

from app.routers import voice as voice_router


def test_post_stt_does_not_shadow_get_supabase_client_import():
    src = inspect.getsource(voice_router.post_stt)
    # Local re-import inside the function body makes the name local for the
    # entire function and breaks the earlier client = get_supabase_client(...).
    assert "from app.billing.service import get_supabase_client" not in src
