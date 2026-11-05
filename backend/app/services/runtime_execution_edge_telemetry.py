"""Opt-in, privacy-bounded execution handoff correlation (PR605 Gate 19).

Never log raw org, user, conversation, run, tool parameters, provider responses,
transcripts or access tokens. Requires a dedicated audit correlation key.
Disabled by default; enabling production collection requires separate review.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Literal

logger = logging.getLogger("app.runtime_execution_edges")

Owner = Literal["agent", "play", "workflow", "connector", "event_consumer", "outcome", "voice"]
Stage = Literal["selected", "started", "authorized", "observed", "completed", "failed", "skipped"]

_ALLOWED_OWNERS = frozenset(("agent", "play", "workflow", "connector", "event_consumer", "outcome", "voice"))
_ALLOWED_STAGES = frozenset(("selected", "started", "authorized", "observed", "completed", "failed", "skipped"))


def emit_handoff(*, owner: str, stage: str, correlation_id: str | None = None,
                 source: str = "") -> bool:
    """Return whether a privacy-safe evidence log was emitted.

    The caller supplies a stable existing run/turn/event correlation identifier,
    which is HMAC-pseudonymized for inter-system handoff correlation.
    Source is a fixed code label, never an arbitrary tool/handler/payload string.
    """
    if os.environ.get("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "").lower() != "true":
        return False
    secret = os.environ.get("PR605_EXECUTION_EDGE_HMAC_KEY", "")
    if len(secret) < 32 or not correlation_id:
        return False
    if owner not in _ALLOWED_OWNERS or stage not in _ALLOWED_STAGES:
        return False
    if not source or len(source) > 64 or not source.replace("_", "").isalnum() or not source.isascii():
        return False
    digest = hmac.new(secret.encode("utf-8"), correlation_id.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    logger.info("runtime_edge_v1 owner=%s stage=%s source=%s correlation=%s",
                owner, stage, source, digest)
    return True
