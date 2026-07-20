"""Post-hoc grounding validation for generated answers."""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_HEURISTIC,
    CONFIDENCE_SOURCE_INSUFFICIENT,
    CONFIDENCE_SOURCE_MODEL,
    label_confidence,
)
from app.services.model_router import TaskType, get_model_router

logger = get_logger(__name__)

SAFE_FALLBACK = (
    "I found related information, but not enough reliable context to answer confidently. "
    "Could you clarify what you need or point me to a specific document or record?"
)

_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _context_block(chunks: list[dict[str, Any]], *, limit: int = 6) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks[:limit], start=1):
        title = chunk.get("source") or chunk.get("title") or f"Source {index}"
        content = str(chunk.get("content") or chunk.get("snippet") or "").strip()[:700]
        if content:
            lines.append(f"[{index}] {title}: {content}")
    return "\n".join(lines) or "(no retrieved context)"


async def validate_grounded_answer(
    answer: str,
    retrieved_context: list[dict[str, Any]],
    *,
    confidence_threshold: float = 0.4,
    org_id: str | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """
    Check whether answer claims trace to retrieved context using a fast model call.
    Returns {is_valid, issues, requires_human, confidence}.
    """
    text = (answer or "").strip()
    if not text:
        return {
            "is_valid": False,
            "issues": ["empty_answer"],
            "requires_human": True,
            **label_confidence(0.0, source=CONFIDENCE_SOURCE_INSUFFICIENT, is_estimate=False),
        }
    if not retrieved_context:
        return {
            "is_valid": False,
            "issues": ["no_retrieved_context"],
            "requires_human": True,
            **label_confidence(0.1, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        }

    prompt = (
        "You are a grounding validator. Decide if the ANSWER is supported by CONTEXT.\n"
        "Flag unsupported factual claims, invented entities, or numbers not present in context.\n\n"
        f"CONTEXT:\n{_context_block(retrieved_context)}\n\n"
        f"ANSWER:\n{text[:4000]}\n\n"
        'Respond JSON only: {"is_valid": true/false, "issues": ["..."], "confidence": 0.0-1.0, '
        '"requires_human": true/false}'
    )
    try:
        router = get_model_router(settings)
        response = await router.complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt="Validate grounding strictly. JSON only.",
            org_id=org_id,
            temperature=0.0,
            max_tokens=300,
        )
        match = _JSON_BLOCK.search(response.content or "")
        if match:
            parsed = json.loads(match.group(0))
            confidence = float(parsed.get("confidence") or 0.0)
            is_valid = bool(parsed.get("is_valid")) and confidence >= confidence_threshold
            return {
                "is_valid": is_valid,
                "issues": list(parsed.get("issues") or []),
                "requires_human": bool(parsed.get("requires_human")) or not is_valid,
                **label_confidence(
                    max(0.0, min(1.0, confidence)),
                    source=CONFIDENCE_SOURCE_MODEL,
                    is_estimate=True,
                ),
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("answer validation skipped org_id=%s error=%s", org_id, exc)

    return {
        "is_valid": True,
        "issues": [],
        "requires_human": False,
        **label_confidence(0.5, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
    }
