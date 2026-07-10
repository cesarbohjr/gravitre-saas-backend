"""Output-side registration contract — write actions must produce verifiable completion payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.connector_output_verified_batches import (
    CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS,
    CLEARED_OUTPUT_SCHEMA_ACTIONS,
)
from app.services.conversational_execution_service import ExecutionResult

OutputDebtKind = Literal["pending_output_schema"]

# Final-segment tokens that mark an advanced action as write-like / mutating.
MUTATING_ADVANCED_VERB_TOKENS: frozenset[str] = frozenset(
    {
        "create",
        "update",
        "send",
        "add",
        "delete",
        "post",
        "insert",
        "upload",
        "reply",
        "comment",
        "remove",
        "set",
        "append",
        "put",
        "track",
        "trigger",
        "enable",
        "schedule",
        "submit",
        "publish",
        "close",
        "resolve",
        "merge",
        "acknowledge",
        "activate",
        "upsert",
        "exchange",
        "apply",
        "request",
        "run",
        "share",
        "copy",
        "watch",
        "note",
        "tag",
        "enroll",
        "invite",
        "assign",
        "cancel",
        "void",
        "refund",
        "pause",
        "resume",
        "archive",
        "restore",
        "approve",
        "reject",
        "complete",
        "start",
        "stop",
        "sync",
        "import",
        "export",
        "transfer",
        "move",
        "rename",
        "attach",
        "detach",
        "link",
        "unlink",
        "grant",
        "revoke",
        "rotate",
        "reset",
        "provision",
        "checkout",
        "book",
        "reserve",
        "release",
        "escalate",
        "reopen",
        "snooze",
        "forward",
        "draft",
        "queue",
        "replay",
        "renew",
        "extend",
        "clone",
        "fork",
        "subscribe",
        "confirm",
        "accept",
        "decline",
        "retry",
        "abort",
        "expire",
        "promote",
        "install",
        "upgrade",
        "patch",
        "scale",
        "resize",
        "dispatch",
        "reassign",
        "reschedule",
        "autofill",
        "exports",
    }
)

# Seed set (hand-tuned mappers) plus write + advanced batches cleared via generic summarizer.
_SEED_VERIFIED_OUTPUT_ACTIONS: frozenset[str] = frozenset(
    {
        "apollo.lists.create",
        "slack.post_message",
        "hubspot.deals.create",
        "hubspot.contacts.create",
        "github.issues.create",
        "zendesk.tickets.create",
        "jira.issues.create",
        "gmail.messages.send",
        "engagebay.contacts.create",
        "engagebay.contacts.update",
    }
)

VERIFIED_OUTPUT_ACTIONS: frozenset[str] = (
    _SEED_VERIFIED_OUTPUT_ACTIONS
    | CLEARED_OUTPUT_SCHEMA_ACTIONS
    | CLEARED_ADVANCED_OUTPUT_SCHEMA_ACTIONS
)


@dataclass(frozen=True)
class OutputAllowlistBucket:
    kind: OutputDebtKind
    label: str
    allowlist: frozenset[str]
    actual: frozenset[str]

    @property
    def stale_entries(self) -> frozenset[str]:
        return frozenset(self.allowlist - self.actual)

    @property
    def unmanaged_debt(self) -> frozenset[str]:
        return frozenset(self.actual - self.allowlist)

    @property
    def is_exact_match(self) -> bool:
        return not self.stale_entries and not self.unmanaged_debt

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "allowlistCount": len(self.allowlist),
            "actualCount": len(self.actual),
            "staleCount": len(self.stale_entries),
            "unmanagedCount": len(self.unmanaged_debt),
            "isExactMatch": self.is_exact_match,
        }


def _action_key(spec: Any) -> str:
    return spec.id if "." in spec.id else spec.tool


def _is_mutating_advanced(action_key: str) -> bool:
    verb = action_key.rsplit(".", 1)[-1].lower()
    return any(token in verb for token in MUTATING_ADVANCED_VERB_TOKENS)


def collect_write_action_keys() -> frozenset[str]:
    """Catalog write actions plus advanced write-like (mutating) actions."""
    keys: set[str] = set()
    for spec in all_catalog_action_specs():
        key = _action_key(spec)
        if spec.kind == "write":
            keys.add(key)
        elif spec.kind == "advanced" and _is_mutating_advanced(key):
            keys.add(key)
    return frozenset(keys)


def collect_pending_output_schemas() -> frozenset[str]:
    return collect_write_action_keys() - VERIFIED_OUTPUT_ACTIONS


def assert_execution_result_verifiable(result: ExecutionResult) -> None:
    """Completed write actions must surface inline value or a resolvable deep link."""
    if not result.success:
        return
    body = str(result.body or "").strip()
    if body or result.result_url:
        return
    raise AssertionError(
        "ExecutionResult success=true requires non-empty body or non-null result_url "
        f"(entity_type={result.entity_type}, integration={result.integration})"
    )


def verify_output_contract() -> list[OutputAllowlistBucket]:
    from app.services.connector_allowlists import PENDING_OUTPUT_SCHEMA_ALLOWLIST

    return [
        OutputAllowlistBucket(
            kind="pending_output_schema",
            label="Write actions missing verified output schema",
            allowlist=PENDING_OUTPUT_SCHEMA_ALLOWLIST,
            actual=collect_pending_output_schemas(),
        )
    ]


def output_contract_summary() -> dict[str, Any]:
    from app.services.connector_allowlists import PENDING_OUTPUT_SCHEMA_ALLOWLIST

    buckets = verify_output_contract()
    pending = buckets[0]
    return {
        "verifiedOutputActions": len(VERIFIED_OUTPUT_ACTIONS),
        "pendingOutputSchemaRemaining": len(PENDING_OUTPUT_SCHEMA_ALLOWLIST),
        "pendingOutputSchemaUnmanaged": len(pending.unmanaged_debt),
        "pendingOutputSchemaStale": len(pending.stale_entries),
        "allExactMatches": all(bucket.is_exact_match for bucket in buckets),
        "buckets": [bucket.to_dict() for bucket in buckets],
    }


def assert_output_contract(*, enforce_pending_output_schema: bool = True) -> None:
    buckets = verify_output_contract()
    failures: list[str] = []
    for bucket in buckets:
        if bucket.stale_entries:
            failures.append(
                f"{bucket.label}: stale allowlist entries (fixed but not removed): "
                f"{sorted(bucket.stale_entries)[:8]}"
                + (" …" if len(bucket.stale_entries) > 8 else "")
            )
        if enforce_pending_output_schema and bucket.unmanaged_debt:
            failures.append(
                f"{bucket.label}: unmanaged debt (add to PENDING_OUTPUT_SCHEMA_ALLOWLIST): "
                f"{sorted(bucket.unmanaged_debt)[:8]}"
                + (" …" if len(bucket.unmanaged_debt) > 8 else "")
            )
    if failures:
        raise AssertionError("Connector output contract failed:\n" + "\n".join(failures))
