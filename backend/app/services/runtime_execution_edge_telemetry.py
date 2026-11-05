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
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger("app.runtime_execution_edges")

Owner = Literal["agent", "play", "workflow", "connector", "event_consumer", "outcome", "voice"]
Stage = Literal["selected", "started", "authorized", "observed", "completed", "failed", "skipped"]

_ALLOWED_OWNERS = frozenset(("agent", "play", "workflow", "connector", "event_consumer", "outcome", "voice"))
_ALLOWED_STAGES = frozenset(("selected", "started", "authorized", "observed", "completed", "failed", "skipped"))


@dataclass(frozen=True)
class ExecutionCorrelation:
    """Typed execution identity; propagate only when IDs belong to the same plan.

    Event primary keys must not be treated as plan IDs without an explicit link.
    This object never serializes or logs the raw identifier.
    """
    execution_id: str

    @classmethod
    def from_plan_id(cls, plan_id: str | None) -> "ExecutionCorrelation | None":
        value = str(plan_id or "").strip()
        return cls(value) if value else None

    @classmethod
    def from_run_id(cls, run_id: str | None) -> "ExecutionCorrelation | None":
        value = str(run_id or "").strip()
        return cls(value) if value else None

    def record(self, *, owner: str, stage: str, source: str) -> bool:
        return emit_handoff(owner=owner, stage=stage,
                            correlation_id=self.execution_id, source=source)


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

_RUN_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def emit_outbox_run_link(*, event_id: str | None, aggregate_type: str,
                         aggregate_id: str | None, event_type: str) -> bool:
    """Link a *claimed, typed* Postgres workflow-run outbox row to its owning run.

    The DB trigger in 20261012024141_domain_event_outbox.sql inserts
    aggregate_type='workflow_run', aggregate_id=NEW.id::text for
    execution.outcome_finalized. Never infer links for arbitrary events or
    from payload/timestamp coincidences.
    """
    if os.environ.get("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "").lower() != "true":
        return False
    secret = os.environ.get("PR605_EXECUTION_EDGE_HMAC_KEY", "")
    if len(secret) < 32:
        return False
    if event_type != "execution.outcome_finalized" or aggregate_type != "workflow_run":
        return False
    event = str(event_id or "").strip()
    run = str(aggregate_id or "").strip()
    if not event.isdecimal() or len(event) > 20 or not _RUN_UUID.fullmatch(run):
        return False
    key = secret.encode("utf-8")
    event_digest = hmac.new(key, event.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    run_digest = hmac.new(key, run.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    logger.info("runtime_edge_link_v1 kind=workflow_run_outbox event=%s run=%s",
                event_digest, run_digest)
    return True


def emit_plan_run_link(*, plan_id: str | None, run_id: str | None,
                       source: str) -> bool:
    """Only call at a boundary holding both genuine persisted identities.

    Never derive either identifier from the other, use timestamps, or serialize
    plaintext. The caller must prove the plan-to-run association in source.
    """
    if os.environ.get("PR605_EXECUTION_EDGE_TELEMETRY_ENABLED", "").lower() != "true":
        return False
    secret = os.environ.get("PR605_EXECUTION_EDGE_HMAC_KEY", "")
    if len(secret) < 32 or source != "orchestration_step":
        return False
    plan = str(plan_id or "").strip()
    run = str(run_id or "").strip()
    if not plan or len(plan) > 256 or not _RUN_UUID.fullmatch(run):
        return False
    key = secret.encode("utf-8")
    plan_digest = hmac.new(key, plan.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    run_digest = hmac.new(key, run.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    logger.info("runtime_edge_link_v1 kind=orchestration_plan_run plan=%s run=%s",
                plan_digest, run_digest)
    return True
