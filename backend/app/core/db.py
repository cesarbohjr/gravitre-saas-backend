"""Canonical Supabase (service-role) client factory.

Lives in app.core so the AI core and other layers don't have to import it from
app.workflows. Returns a service-role client (bypasses RLS) for backend writes.
"""
from __future__ import annotations

from supabase import Client, create_client

from app.config import Settings


def get_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
