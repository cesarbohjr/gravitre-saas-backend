"""Outcome Ownership — one verification vocabulary for every completion decision.

Gravitre already proves writes against the source of record
(``write_success_verification`` → entity_get / field_assert / membership). This
module is the single place that:

* decides whether an action is consequential (a write per the ActionSpec catalog),
* runs the declared source-of-record check synchronously when a caller needs the
  proof before it can truthfully report (workflows, orchestration steps), and
* reads verification evidence back out of observations, step outputs, run
  metadata and agent results.

Readers never trust a bare ``verified: true``. Evidence counts only when it names
the verifier that produced it (``method`` / ``kind`` / ``read_action``), so a
provider payload or a model-authored dict cannot upgrade an outcome to complete.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Keys a real verifier stamps. At least one must be present next to verified=True.
_VERIFIER_KEYS = ("method", "kind", "read_action", "mode")

# Workflow step types whose execution changes something outside Gravitre.
MUTATING_STEP_TYPES = frozenset({"email_send", "slack_post_message", "webhook_post"})
# Step types that delegate to another runtime whose effects need their own proof.
DELEGATING_STEP_TYPES = frozenset({"agent", "council"})


@dataclass(frozen=True)
class VerificationEvidence:
    """Structured source-of-record evidence for one consequential action."""

    verified: bool
    method: str
    action: str | None = None
    read_action: str | None = None
    resource_id: str | None = None
    field: str | None = None
    expected: str | None = None
    observed: str | None = None
    effect: str | None = None
    detail: str | None = None
    follow_up_attempted: bool = False
    verified_at: str = dc_field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def mismatch(self) -> bool:
        detail = str(self.detail or "").lower()
        return detail.startswith("entity_id_mismatch") or detail == "field_value_mismatch"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "verified": self.verified,
            "method": self.method,
            "verified_at": self.verified_at,
            "follow_up_attempted": self.follow_up_attempted,
        }
        for key in ("action", "read_action", "resource_id", "field", "expected", "observed", "effect", "detail"):
            value = getattr(self, key)
            if value not in (None, ""):
                out[key] = value
        if self.resource_id:
            out.setdefault("entity_id", self.resource_id)
        return out


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4096)
def is_write_action(invoke_action: str | None) -> bool:
    """Catalog-driven write classification (shared with the approval gate)."""
    action = str(invoke_action or "").strip().lower()
    if not action:
        return False
    try:
        from app.services.catalog_write_authority import invoke_action_requires_write_approval

        return bool(invoke_action_requires_write_approval(action))
    except Exception:  # noqa: BLE001 — classification must not break execution
        from app.services.connector_outcome_effects import is_mutating_action

        return is_mutating_action(action)


def step_action(step: dict[str, Any] | None) -> str:
    """Invoke action recorded on a workflow step row or config."""
    row = step if isinstance(step, dict) else {}
    for container in (row, row.get("config"), row.get("output_snapshot"), row.get("input_snapshot")):
        if not isinstance(container, dict):
            continue
        nested_cfg = container.get("config") if isinstance(container.get("config"), dict) else {}
        for key in ("invoke_action", "action", "tool_action"):
            value = container.get(key) or nested_cfg.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def step_is_consequential(step_type: str | None, action: str | None = None) -> bool:
    """True when a workflow step's success claims an external effect."""
    kind = str(step_type or "").strip().lower()
    if kind in MUTATING_STEP_TYPES or kind in DELEGATING_STEP_TYPES:
        return True
    if kind == "invoke_tool":
        return is_write_action(action)
    return False


# ---------------------------------------------------------------------------
# Reading evidence
# ---------------------------------------------------------------------------


def _evidence_dict(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    nested = obj.get("verification")
    if isinstance(nested, dict):
        return nested
    return None


def evidence_is_verified(obj: Any) -> bool:
    """The single reader: positive, attributable source-of-record proof only.

    Accepts either a verification record itself or a container carrying one under
    ``verification``. A bare boolean (or a provider body that happens to contain a
    ``verified`` key) is never enough.
    """
    if not isinstance(obj, dict):
        return False
    candidates = []
    nested = _evidence_dict(obj)
    if nested is not None:
        candidates.append(nested)
    if any(k in obj for k in _VERIFIER_KEYS):
        candidates.append(obj)
    for record in candidates:
        if record.get("verified") is True and any(record.get(k) for k in _VERIFIER_KEYS):
            return True
    return False


def evidence_from(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    nested = _evidence_dict(obj)
    if nested is not None:
        return nested
    if any(k in obj for k in _VERIFIER_KEYS):
        return obj
    return None


def evidence_is_mismatch(obj: Any) -> bool:
    record = evidence_from(obj) or {}
    detail = str(record.get("detail") or "").lower()
    return detail.startswith("entity_id_mismatch") or detail == "field_value_mismatch"


# ---------------------------------------------------------------------------
# Producing evidence
# ---------------------------------------------------------------------------


def verify_write_now(
    *,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    request_params: dict[str, Any] | None = None,
    ctx: Any = None,
    client: Any = None,
    org_id: str | None = None,
    settings: Any = None,
    environment_name: str = "production",
    settle: bool = True,
) -> VerificationEvidence:
    """Run the declared source-of-record check for one write, synchronously.

    Never raises. ``verified`` is True only when the provider read returned the
    written entity / requested value / membership.
    """
    action = str(invoke_action or "").strip().lower()
    if not action:
        return VerificationEvidence(False, "none", detail="no_invoke_action")
    try:
        from app.services.collection_population_verify import (
            is_population_write_action,
            verify_collection_population,
        )
        from app.services.write_success_verification import resolve_success_verification

        if is_population_write_action(action):
            pop = verify_collection_population(
                invoke_action=action,
                result_data=result_data,
                client=client,
                org_id=org_id,
                settings=settings,
                environment_name=environment_name,
                ctx=ctx,
            )
            return VerificationEvidence(
                verified=bool(pop.verified),
                method="membership",
                action=action,
                effect=getattr(pop, "effect", None),
                detail=getattr(pop, "detail", None),
                observed=(
                    str(pop.membership_count) if getattr(pop, "membership_count", None) is not None else None
                ),
                follow_up_attempted=bool(getattr(pop, "follow_up_attempted", False)),
            )
        spec = resolve_success_verification(action)
        if spec.mode == "follow_up_field_assert":
            from app.services.field_assert_verify import verify_field_assert

            fa = verify_field_assert(
                invoke_action=action,
                result_data=result_data,
                request_params=request_params,
                ctx=ctx,
                settle=settle,
            )
            return VerificationEvidence(
                verified=bool(fa.verified),
                method="field_assert",
                action=action,
                read_action=getattr(fa, "read_action", None),
                resource_id=getattr(fa, "entity_id", None),
                field=getattr(fa, "field", None),
                expected=getattr(fa, "expected", None),
                observed=getattr(fa, "observed", None),
                effect=getattr(fa, "effect", None),
                detail=getattr(fa, "detail", None),
                follow_up_attempted=bool(getattr(fa, "follow_up_attempted", False)),
            )
        if spec.mode == "follow_up_entity_get":
            from app.services.entity_get_verify import verify_entity_get

            eg = verify_entity_get(
                invoke_action=action, result_data=result_data, ctx=ctx, settle=settle
            )
            evidence = VerificationEvidence(
                verified=bool(eg.verified),
                method="entity_get",
                action=action,
                read_action=eg.read_action,
                resource_id=eg.entity_id,
                effect=eg.effect,
                detail=eg.detail,
                follow_up_attempted=bool(eg.follow_up_attempted),
            )
            if evidence.verified:
                # Existence is proven; for updates, also prove the requested
                # values landed when the request names comparable fields.
                return _assert_requested_fields(evidence, ctx=ctx, request_params=request_params)
            return evidence
        receipt = _send_receipt(action, result_data)
        if receipt is not None:
            return receipt
        return VerificationEvidence(
            False,
            "none",
            action=action,
            detail="no_source_of_record_check_declared",
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("verify_write_now_failed action=%s err=%s", action, exc)
        return VerificationEvidence(False, "error", action=action, detail=f"verifier_error:{type(exc).__name__}")


# Message sends are synchronous creates in the provider's own store: the message
# id / timestamp the provider returns *is* the record. Async job submissions
# (202 + job id) are not sends and never match these verbs.
_SEND_VERBS = ("send", "post_message", "reply", "forward", "post")
_RECEIPT_KEYS = ("message_id", "messageId", "ts", "id", "threadId", "thread_id")


def _send_receipt(action: str, result_data: dict[str, Any] | None) -> VerificationEvidence | None:
    verb = action.rsplit(".", 1)[-1]
    if not any(verb == v or verb.startswith(f"{v}_") or verb.endswith(f"_{v}") for v in _SEND_VERBS):
        return None
    if action.startswith(("webhook.", "http.")):
        return None  # an arbitrary endpoint's 2xx is not a provider record
    data = result_data if isinstance(result_data, dict) else {}
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    if data.get("ok") is False or str(data.get("status") or "").lower() in {"queued", "accepted", "pending"}:
        return None
    for container in (data, nested):
        for key in _RECEIPT_KEYS:
            value = container.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return VerificationEvidence(
                    True,
                    "provider_receipt",
                    action=action,
                    resource_id=str(value).strip(),
                    field=key,
                    detail="provider_returned_message_record",
                )
    return None


_SKIP_ASSERT_KEYS = frozenset(
    {
        "id", "connector_id", "object_id", "contact_id", "company_id", "deal_id", "ticket_id",
        "list_id", "record_id", "entity_id", "properties", "associations", "upstream_outputs",
        "intent_text", "prompt", "config", "metadata", "idempotency_key",
    }
)


def _flatten_requested(params: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    data = params if isinstance(params, dict) else {}
    props = data.get("properties") if isinstance(data.get("properties"), dict) else {}
    for source in (data, props):
        for key, value in source.items():
            if key in _SKIP_ASSERT_KEYS or key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool)) and str(value).strip():
                out[str(key)] = str(value).strip()
    return out


def _values_match(observed: Any, expected: str) -> bool:
    left = str(observed).strip().lower()
    right = str(expected).strip().lower()
    if left == right:
        return True
    try:
        return float(left) == float(right)
    except ValueError:
        return False


def _assert_requested_fields(
    evidence: VerificationEvidence,
    *,
    ctx: Any,
    request_params: dict[str, Any] | None,
) -> VerificationEvidence:
    """Upgrade entity existence to postcondition proof by comparing requested fields.

    Uses the same declared sibling GET. Fields the read does not return are not
    held against the write (many vendors omit unrequested properties), but any
    returned field that disagrees with the request is a mismatch.
    """
    requested = _flatten_requested(request_params)
    if not requested or not evidence.read_action or not evidence.resource_id or ctx is None:
        return evidence
    try:
        from app.services.entity_get_verify import id_param_candidates
        from app.services.field_assert_verify import find_stored_value
        from app.services.sealed_read_execution import invoke_compiled_read

        connector_id = getattr(ctx, "connector_id", None)
        for param_name in id_param_candidates(evidence.read_action):
            params: dict[str, Any] = {param_name: evidence.resource_id}
            if connector_id:
                params["connector_id"] = connector_id
            out = invoke_compiled_read(ctx, evidence.read_action, params)
            if not getattr(out, "success", False):
                continue
            payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
            compared: list[str] = []
            for key, expected in requested.items():
                observed = find_stored_value(payload, key)
                if observed is None:
                    continue
                if not _values_match(observed, expected):
                    # Not a declared assert field, so vendor formatting (phone,
                    # enum labels vs ids) could differ legitimately: report the
                    # outcome as unproven rather than failed.
                    return VerificationEvidence(
                        verified=False,
                        method="entity_get+field_assert",
                        action=evidence.action,
                        read_action=evidence.read_action,
                        resource_id=evidence.resource_id,
                        field=key,
                        expected=expected,
                        observed=str(observed),
                        effect=evidence.effect,
                        detail="requested_field_differs",
                        follow_up_attempted=True,
                    )
                compared.append(key)
            if compared:
                return VerificationEvidence(
                    verified=True,
                    method="entity_get+field_assert",
                    action=evidence.action,
                    read_action=evidence.read_action,
                    resource_id=evidence.resource_id,
                    field=",".join(sorted(compared)),
                    effect=evidence.effect,
                    detail="follow_up_fields_confirmed",
                    follow_up_attempted=True,
                )
            return evidence
    except Exception as exc:  # noqa: BLE001
        logger.debug("field_postcondition_assert_skipped action=%s err=%s", evidence.action, exc)
    return evidence


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeRollup:
    """Truthful aggregate over the consequential children of one objective."""

    consequential: int
    verified: int
    unverified: int
    failed: int
    mismatched: int
    succeeded: int

    @property
    def status(self) -> str:
        """completed | partial_success | verification_inconclusive | failed."""
        if self.failed and not self.succeeded:
            return "failed"
        if self.failed or self.mismatched:
            return "partial_success" if (self.verified or self.succeeded) else "failed"
        if self.unverified:
            return "verification_inconclusive"
        return "completed"

    def as_dict(self) -> dict[str, Any]:
        return {
            "consequential": self.consequential,
            "verified": self.verified,
            "unverified": self.unverified,
            "failed": self.failed,
            "mismatched": self.mismatched,
            "succeeded": self.succeeded,
            "status": self.status,
        }


def rollup(children: Iterable[dict[str, Any]]) -> OutcomeRollup:
    """Each child: {"consequential": bool, "success": bool, "skipped": bool, evidence…}."""
    consequential = verified = unverified = failed = mismatched = succeeded = 0
    for child in children:
        if not isinstance(child, dict) or child.get("skipped"):
            continue
        if child.get("consequential") and is_uncertain(child):
            # The effect may exist: neither a failure nor a proven success.
            consequential += 1
            unverified += 1
            continue
        ok = bool(child.get("success"))
        if ok:
            succeeded += 1
        else:
            failed += 1
        if not child.get("consequential"):
            continue
        consequential += 1
        if not ok:
            continue
        if evidence_is_mismatch(child):
            mismatched += 1
        elif evidence_is_verified(child):
            verified += 1
        else:
            unverified += 1
    return OutcomeRollup(consequential, verified, unverified, failed, mismatched, succeeded)


def is_uncertain(obj: Any) -> bool:
    """True when a write's provider-side effect is unknown (ambiguous delivery)."""
    if not isinstance(obj, dict):
        return False
    if obj.get("outcome_uncertain") is True:
        return True
    return str(obj.get("error_code") or "").strip().lower() == "outcome_uncertain"


def child_from_tool_call(call: dict[str, Any] | None) -> dict[str, Any]:
    """Rollup child for one registry tool call recorded by ReAct / agents."""
    row = call if isinstance(call, dict) else {}
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    action = str(result.get("action") or row.get("action") or row.get("invoke_action") or "")
    child: dict[str, Any] = {
        "action": action,
        "consequential": is_write_action(action) if action else False,
        "success": result.get("success") is True,
    }
    if isinstance(result.get("verification"), dict):
        child["verification"] = result["verification"]
    if is_uncertain(result):
        child["outcome_uncertain"] = True
    return child


def outcome_from_tool_calls(tool_calls: Iterable[dict[str, Any]] | None) -> OutcomeRollup:
    """Truthful outcome of an agent / ReAct run from its recorded tool calls.

    Only writes count: a failed exploratory read that the agent recovered from is
    not a partial outcome. With no writes the rollup is ``completed`` and the
    agent's answer is the deliverable.
    """
    children = (child_from_tool_call(call) for call in (tool_calls or []))
    return rollup(child for child in children if child["consequential"])
