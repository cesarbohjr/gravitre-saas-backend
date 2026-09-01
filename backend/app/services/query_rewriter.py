"""Context-aware query rewriting for retrieval (distinct from v2 normalization)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router

logger = get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


async def rewrite_for_retrieval(
    query: str,
    conversation_history: list[dict[str, Any]] | None,
    *,
    org_id: str | None = None,
    settings: Any | None = None,  # accepted for caller compatibility; get_model_router takes none
) -> dict[str, str]:
    """
    Expand a vague query using recent conversation context for hybrid retrieval only.
    Returns original_query and refined_query; on failure refined_query equals original.
    """
    original = (query or "").strip()
    if not original:
        return {"original_query": "", "refined_query": "", "model_ran": False}

    history = conversation_history or []
    recent_lines: list[str] = []
    for message in history[-6:]:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            recent_lines.append(f"{role}: {content[:400]}")

    if not recent_lines:
        return {"original_query": original, "refined_query": original, "model_ran": False}

    history_block = "\n".join(recent_lines)
    prompt = (
        "Rewrite the user's latest message into a standalone search query optimized for "
        "internal document retrieval. Preserve intent and named entities from the conversation. "
        "Do not answer the question.\n\n"
        f"Conversation:\n{history_block}\n\n"
        f"Latest user message:\n{original}\n\n"
        'Respond with JSON only: {"refined_query": "..."}'
    )
    # model_ran distinguishes "the model judged and declined to rewrite" from
    # "the call never happened", which are identical in the returned query and
    # were indistinguishable for the whole time this call was dormant.
    model_ran = False
    try:
        router = get_model_router()
        response = await router.complete(
            task_type=TaskType.INTENT_DETECTION,
            prompt=prompt,
            system_prompt="You rewrite queries for search. Output JSON only.",
            org_id=org_id,
            temperature=0.0,
            max_tokens=256,
        )
        model_ran = True
        match = _JSON_BLOCK.search(response.content or "")
        if match:
            parsed = json.loads(match.group(0))
            refined = str(parsed.get("refined_query") or "").strip()
            if refined and refined.lower() != original.lower():
                return {
                    "original_query": original,
                    "refined_query": refined[:2000],
                    "model_ran": True,
                }
    except Exception as exc:  # noqa: BLE001
        logger.warning("query rewrite skipped org_id=%s error=%s", org_id, exc)

    return {"original_query": original, "refined_query": original, "model_ran": model_ran}
