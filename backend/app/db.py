"""FastAPI dependency for Supabase client access."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.config import Settings, get_settings
from app.core.db import get_supabase_client


def get_supabase(settings: Annotated[Settings, Depends(get_settings)]) -> Client:
    return get_supabase_client(settings)
