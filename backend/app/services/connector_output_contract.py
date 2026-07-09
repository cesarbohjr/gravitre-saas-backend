"""Output-side registration contract — write actions must produce verifiable completion payloads."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.connectors.action_catalog.registry import all_catalog_action_specs
from app.services.conversational_execution_service import ExecutionResult

OutputDebtKind = Literal["pending_output_schema"]

# Write actions with tested inline summaries and/or resolvable result_url behavior.
VERIFIED_OUTPUT_ACTIONS: frozenset[str] = frozenset(
    {
        "apollo.lists.create",
        "slack.post_message",
        "hubspot.deals.create",
        "hubspot.contacts.create",
        "github.issues.create",
        "zendesk.tickets.create",
        "jira.issues.create",
        "gmail.messages.send",
    }
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


def collect_write_action_keys() -> frozenset[str]:
    return frozenset(
        spec.id if "." in spec.id else spec.tool
        for spec in all_catalog_action_specs()
        if spec.kind == "write"
    )


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
