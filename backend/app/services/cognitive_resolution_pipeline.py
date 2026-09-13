"""Phase A resolution pipeline: semantic → reference → resource → clarification."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.services.clarification_policy import ClarificationDecision, decide_from_resource_resolution
from app.services.connector_resource_resolver import ResourceResolution, ResourceResolutionRequest, resolve_resource_request
from app.services.connector_semantic_registry import (
    resolve_all_connectors_from_text,
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)
from app.services.reference_resolver import ReferenceResolution, resolve_reference
from app.services.resolution_trace_service import ResolutionTrace, ResolutionTraceBuilder


@dataclass(frozen=True)
class CognitiveResolutionResult:
    connector_id: str | None
    connector_ids: tuple[str, ...]
    resource: ResourceResolution | None
    reference: ReferenceResolution
    clarification: ClarificationDecision | None
    trace: ResolutionTrace
    analytics_capabilities: tuple[str, ...]


async def run_cognitive_resolution(
    *,
    message: str,
    task_state: dict[str, Any] | None,
    tenant_id: str,
    user_id: str | None,
    client: Any,
    settings: Settings | None = None,
    conversation_id: str | None = None,
    connected_integrations: list[str] | None = None,
    explicit_connector_id: str | None = None,
    skip_resource: bool = False,
) -> CognitiveResolutionResult:
    """Run Phase A resolution stages for a turn. Does not execute tools or mutate writes."""
    active_settings = settings or get_settings()
    state = task_state if isinstance(task_state, dict) else {}
    builder = ResolutionTraceBuilder(conversation_id=conversation_id, tenant_id=tenant_id)
    builder.mark("turn_received")
    builder.mark("semantic_resolution_start")

    reference = resolve_reference(message, state)
    builder.set_reference(reference.kind if reference.matched else "none", reference.matched)

    connector_id = explicit_connector_id or resolve_connector_from_text(message)
    connector_ids = tuple(resolve_all_connectors_from_text(message))
    if connector_id:
        builder.set_connector(connector_id)
    builder.mark("semantic_resolution_complete", connector_id=connector_id, connector_ids=list(connector_ids))

    analytics_caps = tuple(
        resolve_analytics_capabilities_for_message(
            message,
            connected_integrations=connected_integrations,
        )
    )

    resource: ResourceResolution | None = None
    clarification: ClarificationDecision | None = None
    target_connector = connector_id
    if not target_connector and len(analytics_caps) == 1:
        target_connector = analytics_caps[0]

    if target_connector and not skip_resource:
        builder.mark("resource_resolution_start", connector_id=target_connector)
        request = ResourceResolutionRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            connector_id=target_connector,
            conversation_context=state,
        )
        resource = resolve_resource_request(request, client=client, settings=active_settings)
        builder.set_resource(
            resource_id=resource.resource_id or None,
            candidate_count=resource.candidate_count,
            reason=resource.resolution_reason,
        )
        clarification = decide_from_resource_resolution(resource)
    elif skip_resource and target_connector:
        builder.mark(
            "resource_resolution_complete",
            skipped=True,
            connector_id=target_connector,
        )
        clarification = ClarificationDecision(should_ask=False, reason="no_clarification_needed")

    if clarification is not None:
        builder.set_clarification(clarification.should_ask, clarification.reason)

    trace = builder.finish()
    builder.emit_log()
    return CognitiveResolutionResult(
        connector_id=connector_id,
        connector_ids=connector_ids,
        resource=resource,
        reference=reference,
        clarification=clarification,
        trace=trace,
        analytics_capabilities=analytics_caps,
    )
