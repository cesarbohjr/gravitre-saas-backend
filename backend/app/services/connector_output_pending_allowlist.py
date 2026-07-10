"""Generated pending output schema debt — shrink as actions gain verified summaries/result_url.

Cleared in batches of 25 via ``connector_output_verified_batches.py`` + the generic
write summarizer (2026-07-10). Remaining debt should stay empty unless new write
actions are cataloged without verification.
"""
from __future__ import annotations

PENDING_OUTPUT_SCHEMA_ALLOWLIST: frozenset[str] = frozenset()
