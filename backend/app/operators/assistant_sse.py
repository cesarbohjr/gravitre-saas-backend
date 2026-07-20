"""Map assistant/ReAct streaming events to AI SDK UI SSE chunks."""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.operators.assistant_mode_config import REGISTRY_TO_ASSISTANT_DISPLAY
from app.operators.stream_events import AssistantStreamEvent
from app.services.assistant_tools import TOOL_DISPLAY_NAMES


def _sse(chunk: dict[str, Any]) -> AssistantStreamEvent:
    data = dict(chunk)
    sse_type = str(data.pop("type"))
    return AssistantStreamEvent(sse_type=sse_type, payload=data)


def sse_start() -> AssistantStreamEvent:
    return _sse({"type": "start"})


def sse_start_step() -> AssistantStreamEvent:
    return _sse({"type": "start-step"})


def sse_finish_step() -> AssistantStreamEvent:
    return _sse({"type": "finish-step"})


def sse_finish() -> AssistantStreamEvent:
    return _sse({"type": "finish"})


def sse_done() -> str:
    return "data: [DONE]\n\n"


def sse_error(message: str) -> AssistantStreamEvent:
    return _sse({"type": "error", "errorText": message})


def sse_suggestions(suggestions: list[str]) -> AssistantStreamEvent:
    return _sse({"type": "data-suggestions", "data": {"suggestions": suggestions}})


def sse_intelligence_metadata(
    *,
    message_id: str | None,
    confidence: dict[str, Any] | None,
    answer_explanation: str | None,
    conflicts: list[dict[str, Any]] | None = None,
    refined_query: str | None = None,
    validation: dict[str, Any] | None = None,
    dialogue_mode: str | None = None,
    persona_key: str | None = None,
    proactive_suggestions: list[str] | None = None,
    task_state: dict[str, Any] | None = None,
    simulation_summary: dict[str, Any] | None = None,
    execution_result: dict[str, Any] | None = None,
    pending_task: dict[str, Any] | None = None,
    context_profile: dict[str, Any] | None = None,
    context_explanation: str | None = None,
    business_signals: list[dict[str, Any]] | None = None,
    strategic_plan: dict[str, Any] | None = None,
    knowledge_assignments: list[dict[str, Any]] | None = None,
    assigned_sources_used: list[dict[str, Any]] | None = None,
    knowledge_gap_message: str | None = None,
    missing_assignment_labels: list[str] | None = None,
    memory_conflicts: list[dict[str, Any]] | None = None,
    advisor_brief: dict[str, Any] | None = None,
    explainability: dict[str, Any] | None = None,
    execution_gate: dict[str, Any] | None = None,
    trust_envelope: dict[str, Any] | None = None,
    effective_mode: str | None = None,
    pipeline_tier: str | None = None,
    routing_tier: str | None = None,
    routing: dict[str, Any] | None = None,
    progress_steps: list[str] | None = None,
    tool_visibility: dict[str, Any] | None = None,
    research_cascade: dict[str, Any] | None = None,
    react_perf: dict[str, Any] | None = None,
) -> AssistantStreamEvent:
    return _sse(
        {
            "type": "data-intelligence",
            "data": {
                "messageId": message_id,
                "confidence": confidence,
                "answerExplanation": answer_explanation,
                "conflicts": conflicts or [],
                "refinedQuery": refined_query,
                "validation": validation,
                "dialogueMode": dialogue_mode,
                "personaKey": persona_key,
                "proactiveSuggestions": proactive_suggestions or [],
                "taskState": task_state,
                "simulationSummary": simulation_summary,
                "executionResult": execution_result,
                "pendingTask": pending_task,
                "contextProfile": context_profile,
                "contextExplanation": context_explanation,
                "businessSignals": business_signals or [],
                "strategicPlan": strategic_plan,
                "knowledgeAssignments": knowledge_assignments or [],
                "assignedSourcesUsed": assigned_sources_used or [],
                "knowledgeGapMessage": knowledge_gap_message,
                "missingAssignmentLabels": missing_assignment_labels or [],
                "memoryConflicts": memory_conflicts or [],
                "advisorBrief": advisor_brief,
                "explainability": explainability or {},
                "executionGate": execution_gate or {},
                "trustEnvelope": trust_envelope or {},
                "effectiveMode": effective_mode,
                "pipelineTier": pipeline_tier,
                "routingTier": routing_tier,
                "routing": routing,
                "progressSteps": progress_steps or [],
                "toolVisibility": tool_visibility or {},
                "researchCascade": research_cascade or None,
                "reactPerf": react_perf or None,
            },
        }
    )


def sse_knowledge_base_tool(
    *,
    call_id: str,
    query: str,
    output: dict[str, Any],
) -> list[AssistantStreamEvent]:
    display = TOOL_DISPLAY_NAMES["knowledge_base"]
    return [
        _sse(
            {
                "type": "tool-input-available",
                "toolCallId": call_id,
                "toolName": display,
                "input": {"query": query, "limit": 5},
            }
        ),
        _sse(
            {
                "type": "tool-output-available",
                "toolCallId": call_id,
                "output": output,
            }
        ),
    ]


def sse_react_tool_start(
    *,
    call_id: str,
    registry_tool_name: str,
    tool_args: dict[str, Any] | None,
) -> AssistantStreamEvent:
    display = REGISTRY_TO_ASSISTANT_DISPLAY.get(registry_tool_name) or registry_tool_name
    tool_input: dict[str, Any] = dict(tool_args or {})
    if "query" not in tool_input and registry_tool_name == "web_search":
        tool_input.setdefault("query", tool_args.get("query") if tool_args else "")
    return _sse(
        {
            "type": "tool-input-available",
            "toolCallId": call_id,
            "toolName": display,
            "input": tool_input or {"query": tool_args.get("query", "") if tool_args else ""},
        }
    )


def format_react_tool_output(registry_tool_name: str, observation: dict[str, Any]) -> dict[str, Any]:
    """Shape ToolRegistry observations like legacy assistant_tools outputs for UI chips."""
    if registry_tool_name == "web_search":
        results = observation.get("results") or []
        sources = observation.get("sources") or [
            {"title": row.get("title"), "url": row.get("url"), "excerpt": row.get("snippet")}
            for row in results
            if isinstance(row, dict)
        ]
        query = observation.get("query") or ""
        if observation.get("success") is False:
            return {
                "results": [],
                "totalResults": 0,
                "error": observation.get("error") or "web search unavailable",
                "query": query,
            }
        return {
            "results": results,
            "sources": sources,
            "totalResults": observation.get("totalResults", len(results)),
            "query": query,
        }
    if observation.get("success") is False:
        from app.services.tool_error_messages import format_tool_error_for_user

        error_code = observation.get("error_code")
        raw_error = observation.get("error")
        formatted = format_tool_error_for_user(
            str(error_code) if error_code is not None else None,
            str(raw_error) if raw_error is not None else None,
            integration=observation.get("integration")
            if isinstance(observation.get("integration"), str)
            else None,
            action=(
                observation.get("action")
                if isinstance(observation.get("action"), str)
                else registry_tool_name
            ),
        )
        payload: dict[str, Any] = {
            "error": formatted,
            "success": False,
        }
        if error_code is not None:
            payload["errorCode"] = error_code
        return payload
    payload = observation.get("result")
    if isinstance(payload, dict):
        shaped = dict(payload)
        shaped.setdefault("success", True)
        return shaped
    if isinstance(observation, dict):
        return {**observation, "success": observation.get("success", True)}
    return observation


def sse_react_tool_complete(
    *,
    call_id: str,
    registry_tool_name: str,
    observation: dict[str, Any],
) -> AssistantStreamEvent:
    return _sse(
        {
            "type": "tool-output-available",
            "toolCallId": call_id,
            "output": format_react_tool_output(registry_tool_name, observation),
        }
    )


def sse_text_start(text_id: str | None = None) -> tuple[str, AssistantStreamEvent]:
    resolved = text_id or f"text-{uuid.uuid4().hex[:12]}"
    return resolved, _sse({"type": "text-start", "id": resolved})


def sse_text_delta(text_id: str, delta: str) -> AssistantStreamEvent:
    return _sse({"type": "text-delta", "id": text_id, "delta": delta})


def sse_text_end(text_id: str) -> AssistantStreamEvent:
    return _sse({"type": "text-end", "id": text_id})


def assistant_event_to_sse_line(event: AssistantStreamEvent) -> str:
    return f"data: {json.dumps({'type': event.sse_type, **event.payload}, separators=(',', ':'))}\n\n"


def chunk_text_deltas(text: str, *, size: int = 24) -> list[str]:
    cleaned = text or ""
    if not cleaned:
        return [""]
    return [cleaned[i : i + size] for i in range(0, len(cleaned), size)]
