"""Structured memory extraction — no raw transcript replay as standing knowledge."""
from __future__ import annotations

from typing import Any

from app.services.memory_contamination_guard import (
    SOURCE_MODEL_INFERENCE,
    SOURCE_UNTRUSTED_EXTERNAL,
    SOURCE_WORKFLOW_OUTCOME,
    classify_memory_source,
    looks_like_injection,
    validate_memory_write,
)


def _structured_outcome(
    outcome_event: str,
    act_result: dict[str, Any] | None,
    message: str | None,
) -> dict[str, Any]:
    """Build structured outcome memory from act metadata, not transcript copy."""
    result = act_result if isinstance(act_result, dict) else {}
    payload: dict[str, Any] = {
        "event": outcome_event,
        "status": result.get("status") or result.get("success"),
        "action": result.get("action"),
        "error": (str(result.get("error") or "")[:300] or None),
    }
    if result.get("tool_name"):
        payload["tool_name"] = result.get("tool_name")
    if result.get("connector_id"):
        payload["connector_id"] = result.get("connector_id")

    parts = [f"Outcome ({outcome_event})"]
    if payload.get("action"):
        parts.append(f"action={payload['action']}")
    if payload.get("status") is not None:
        parts.append(f"status={payload['status']}")
    if payload.get("error"):
        parts.append(f"error={payload['error']}")
    summary = "; ".join(parts)

    raw: dict[str, Any] = {
        "content": summary[:4000],
        "category": "outcome",
        "confidence": 70,
        "provenance": f"learn_outcome:{outcome_event}",
        "structured_payload": payload,
        "outcome_event": outcome_event,
    }
    # Message is context only — never the primary stored content.
    if message and len(summary) < 40:
        raw["structured_payload"]["context_hint"] = str(message)[:200]
    return validate_memory_write(raw, provenance=raw["provenance"])


def extract_structured_from_message(
    message: str,
    *,
    category: str = "episodic",
    provenance: str = "structured_extract",
) -> dict[str, Any] | None:
    """Lightweight structured extraction from user text (preference/decision patterns)."""
    text = (message or "").strip()
    if not text or len(text) < 8:
        return None

    lower = text.lower()
    structured: dict[str, Any] = {"source_text_len": len(text)}

    # ICP / preference patterns (example: employee range change)
    if "icp" in lower or "ideal customer" in lower:
        structured["subject"] = "icp"
        category = "preference"
    elif any(k in lower for k in ("prefer", "preference", "we use", "we prefer")):
        structured["subject"] = "preference"
        category = "preference"
    elif any(k in lower for k in ("decided", "decision", "we will", "standing")):
        structured["subject"] = "decision"
        category = "decision"

    # Extract employee-range style facts when present
    import re

    range_match = re.search(r"(\d+)\s*[-–to]+\s*(\d+)\s*employees?", lower)
    if range_match:
        structured["employee_range"] = {
            "min": int(range_match.group(1)),
            "max": int(range_match.group(2)),
        }

    content = text[:4000]
    if structured.get("subject") == "icp" and structured.get("employee_range"):
        er = structured["employee_range"]
        content = f"ICP employee range: {er['min']}-{er['max']} employees"

    raw: dict[str, Any] = {
        "content": content,
        "category": category,
        "confidence": 85,
        "provenance": provenance,
        "structured_payload": structured,
        "user_direct": True,
    }
    return validate_memory_write(raw, provenance=provenance)


def extract_typed_memories_structured(
    act_result: dict[str, Any] | None,
    *,
    outcome_event: str | None = None,
    message: str | None = None,
    provenance: str = "",
) -> list[dict[str, Any]]:
    """Structured replacement for raw transcript memory extraction."""
    out: list[dict[str, Any]] = []
    if isinstance(act_result, dict):
        for key in ("typed_memories", "memories", "workspace_memories"):
            raw = act_result.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and (item.get("content") or item.get("memory_text")):
                        enriched = validate_memory_write(
                            {
                                **item,
                                "content": str(item.get("content") or item.get("memory_text")),
                            },
                            provenance=provenance or str(item.get("provenance") or ""),
                        )
                        if item.get("structured_payload"):
                            enriched["structured_payload"] = item["structured_payload"]
                        out.append(enriched)

        content = act_result.get("memory_content") or act_result.get("decision")
        category = str(act_result.get("memory_category") or "").strip().lower()
        if content and category:
            out.append(
                validate_memory_write(
                    {
                        "content": str(content),
                        "category": category,
                        "structured_payload": act_result.get("structured_payload"),
                    },
                    provenance=provenance,
                )
            )

        # Untrusted connector/document payloads — block injection, cap confidence
        ext = act_result.get("external_memory_candidate")
        if isinstance(ext, dict) and ext.get("content"):
            ext_content = str(ext["content"])
            if looks_like_injection(ext_content):
                ext["blocked_injection"] = True
                ext["confidence"] = 10
            ext_row = validate_memory_write(
                {
                    **ext,
                    "from_untrusted_external": True,
                    "category": ext.get("category") or "episodic",
                },
                provenance=str(ext.get("provenance") or "untrusted_external"),
            )
            if ext_row.get("source_class") == SOURCE_UNTRUSTED_EXTERNAL:
                out.append(ext_row)

    if outcome_event:
        out.append(_structured_outcome(outcome_event, act_result, message))
    elif message and not out:
        extracted = extract_structured_from_message(message, provenance=provenance or "turn_extract")
        if extracted:
            out.append(extracted)

    return out
