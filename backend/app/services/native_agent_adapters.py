"""Gravitre-native boundaries for external engineering/browser artifacts and telemetry.

Artifact adapters produce review-only canonical plans, never executable vendor
actions. Caller scope comes from authenticated intake, not provider output.
No SDK is imported, no runtime is launched, and telemetry is opt-in per run.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.core.safe_dict import safe_normalize_stored_dict
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep


@dataclass(frozen=True)
class AdapterScope:
    """Trusted intake identity; never construct this from an external artifact."""
    org_id: str
    agent_id: str
    run_id: str

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in (self.org_id, self.agent_id, self.run_id)):
            raise ValueError("Complete tenant, agent and run scope is required")


def _artifact(payload: Any, scope: AdapterScope) -> dict[str, Any]:
    row = safe_normalize_stored_dict(payload)
    if any(row.get(k) != getattr(scope, k) for k in ("org_id", "agent_id", "run_id")):
        raise ValueError("Artifact scope does not match authenticated intake")
    if row.get("schema_version") != 1 or type(row.get("schema_version")) is not int:
        raise ValueError("Unsupported native artifact schema")
    return row


def _evidence_text(value: Any) -> str:
    # Only strings are accepted. Escaping prevents external text closing an
    # envelope when a plan is serialized into a model prompt.
    return value[:2000].replace("<", "\\u003c").replace(">", "\\u003e") if isinstance(value, str) else ""


def _review_plan(scope: AdapterScope, source: str, evidence: list[dict[str, Any]]) -> ExecutionPlan:
    return ExecutionPlan(
        plan_id=f"{scope.run_id}:{source}:review", source=source,
        summary="Review external observations before planning any action",
        objective="Validate advisory evidence within the existing tenant and tool policy",
        terminal_status="clarification_required",
        steps=[ExecutionStep(
            step_id=f"review_{i}", title="Review untrusted external evidence", kind="clarify",
            meta={"advisory_only": True, "verified": False, "requires_review": True,
                  "org_id": scope.org_id, "agent_id": scope.agent_id, "run_id": scope.run_id,
                  "evidence": item},
        ) for i, item in enumerate(evidence)],
    )


def openhands_review_plan(payload: Any, *, scope: AdapterScope) -> ExecutionPlan:
    """Adapt native intake observations; ignore commands, patches and success claims.

    The native v1 envelope contains `observations: [{summary: str}]`. This is
    explicitly not a promise to accept every OpenHands/ACP SDK event format.
    """
    row = _artifact(payload, scope)
    observations = row.get("observations")
    if not isinstance(observations, list) or not 0 < len(observations) <= 50:
        raise ValueError("Expected 1–50 engineering observations")
    evidence = []
    for observation in observations:
        if not isinstance(observation, dict) or not isinstance(observation.get("summary"), str):
            raise ValueError("Malformed engineering observation")
        evidence.append({"summary": _evidence_text(observation["summary"]), "source": "openhands"})
    return _review_plan(scope, "openhands_native", evidence)


def browser_use_review_plan(payload: Any, *, scope: AdapterScope, allowed_hosts: frozenset[str]) -> ExecutionPlan:
    """Accept bounded observations from an already scoped browser worker.

    No browser session is shared or created here. The worker remains responsible
    for navigation/redirect/network policy. URLs are provenance, never fetched.
    """
    row = _artifact(payload, scope)
    observations = row.get("observations")
    if not isinstance(observations, list) or not 0 < len(observations) <= 50:
        raise ValueError("Expected 1–50 browser observations")
    evidence = []
    for observation in observations:
        if not isinstance(observation, dict) or not isinstance(observation.get("summary"), str):
            raise ValueError("Malformed browser observation")
        url = observation.get("url")
        if not isinstance(url, str) or len(url) > 2048:
            raise ValueError("Missing or oversized browser source URL")
        try:
            parts = urlsplit(url)
            valid = (parts.scheme == "https" and parts.hostname in allowed_hosts
                     and parts.port in (None, 443) and not parts.username and not parts.password
                     and not any(c.isspace() or ord(c) < 32 for c in url) and "\\" not in url)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Browser source outside allowed HTTPS hosts")
        evidence.append({"source": "browser_use", "summary": _evidence_text(observation["summary"]),
                         "url": urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))})
    return _review_plan(scope, "browser_use_native", evidence)


@dataclass(frozen=True)
class TelemetryPermit:
    """Per-run export choice supplied by the host's consent/configuration layer."""
    scope: AdapterScope
    enabled: bool = False


def export_langfuse_run(
    run: Any, *, scope: AdapterScope, permit: TelemetryPermit,
    correlation_key: bytes, langfuse_client: Any,
) -> str:
    """Export only allowlisted run metrics via the current observation interface.

    Prompts, replies, model input/output, source records, IDs, exception text,
    URLs and provider credentials never enter the export. A configured client
    is injected by the host; no default client or new destination is created.
    """
    if permit.scope != scope or permit.enabled is not True:
        return "disabled"
    if not isinstance(correlation_key, bytes) or len(correlation_key) < 32:
        raise ValueError("A dedicated correlation key of at least 32 bytes is required")
    row = safe_normalize_stored_dict(run)
    if row.get("org_id") != scope.org_id or row.get("id") != scope.run_id:
        raise ValueError("Run scope does not match telemetry permit")
    # JSON tuple encoding prevents scope collisions from delimiter characters.
    scoped_id = json.dumps([scope.org_id, scope.agent_id, scope.run_id], separators=(",", ":"))
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "run_ref": hmac.new(correlation_key, scoped_id.encode(), hashlib.sha256).hexdigest(),
        "status": row.get("status") if isinstance(row.get("status"), str) and row.get("status") in {
            "pending", "running", "completed", "failed", "cancelled", "blocked", "partial",
        } else "unknown",
    }
    duration = row.get("duration_ms")
    if type(duration) is int and 0 <= duration <= 604800000:
        metadata["duration_ms"] = duration
    try:
        with langfuse_client.start_as_current_observation(as_type="span", name="gravitre.run") as span:
            span.update(metadata=metadata)
    except Exception:
        # Never attach provider errors to logs, prompts or telemetry. Telemetry
        # failure must not change the business run or claim delivery succeeded.
        return "export_failed"
    return "submitted"


def export_langfuse_feedback(
    client: Any, receipt_id: str, *, scope: AdapterScope, permit: TelemetryPermit,
    correlation_key: bytes, langfuse_client: Any,
) -> str:
    """Submit allowlisted metrics from a verified tenant-local feedback receipt.

    This does not export prompts or claim a durable remote receipt. Local ledger
    readback and remote submission remain separate, observable outcomes.
    """
    if permit.scope != scope or permit.enabled is not True:
        return "disabled"
    if not isinstance(correlation_key, bytes) or len(correlation_key) < 32:
        raise ValueError("A dedicated correlation key of at least 32 bytes is required")
    metadata = load_langfuse_feedback_metrics(client, receipt_id, scope=scope, correlation_key=correlation_key)
    if metadata is None:
        return "receipt_missing"
    try:
        with langfuse_client.start_as_current_observation(as_type="span",name="gravitre.dialogue_evaluation") as span:
            span.update(metadata=metadata)
    except Exception:
        return "export_failed"
    return "submitted"


def load_langfuse_feedback_metrics(client: Any, receipt_id: str, *, scope: AdapterScope, correlation_key: bytes) -> dict[str, Any] | None:
    """Read one exact-scope receipt; return only the export allowlist."""
    if not isinstance(correlation_key, bytes) or len(correlation_key) < 32:
        raise ValueError("A dedicated correlation key of at least 32 bytes is required")
    rows = (client.table("intelligence_outcome_events").select("id,org_id,agent_id,entity_id,outcome_event,metadata")
            .eq("org_id", scope.org_id).eq("agent_id", scope.agent_id).eq("id", receipt_id).eq("outcome_event", "dialogue_evaluated")
            .limit(1).execute().data or [])
    if len(rows) != 1:
        return None
    row = rows[0]
    if row.get("org_id") != scope.org_id or row.get("agent_id") != scope.agent_id or row.get("entity_id") != scope.run_id or row.get("outcome_event") != "dialogue_evaluated":
        raise ValueError("Feedback receipt scope mismatch")
    metrics = safe_normalize_stored_dict(row.get("metadata"))
    if metrics.get("evaluator_version") != "dialogue-metrics-v1" or (not isinstance(metrics.get("channel"), str) or metrics.get("channel") not in {"text", "voice"}):
        raise ValueError("Invalid feedback metrics")
    values = {}
    for key, maximum in (("stage_count",20),("failed_stage_count",20),("duration_ms",604800000)):
        value = metrics.get(key)
        if type(value) is not int or not 0 <= value <= maximum:
            raise ValueError("Invalid feedback metric range")
        values[key] = value
    scoped_id = json.dumps([scope.org_id, scope.agent_id, scope.run_id], separators=(",", ":"))
    metadata = {"schema_version":1, "run_ref":hmac.new(correlation_key,scoped_id.encode(),hashlib.sha256).hexdigest(),
                "channel":metrics["channel"], "evaluator_version":"dialogue-metrics-v1", **values}
    return metadata
