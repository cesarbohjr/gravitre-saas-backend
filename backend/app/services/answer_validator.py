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

# A retrieved chunk is prose and compresses well. A tool result is structured
# data the answer is often a direct restatement of ("you have 3 open deals"),
# so truncating it mid-record is what turns a correct answer into a phantom
# unsupported claim. Tool results therefore get a much larger slice.
_DOC_CHAR_BUDGET = 700
# Raised from 2000 after live measurement at 742414b9. Two of three tool answers
# passed in ~1.4s; the one that was rejected and regenerated (11.9s) was the
# largest payload — "list my hubspot contacts", where the answer enumerated ten
# records. At 2000 chars the tail of that list was cut, so the validator could
# not see the very records the answer named and correctly called them
# unsupported. Truncation was manufacturing false rejections.
_TOOL_CHAR_BUDGET = 6000
# Total ceiling so a multi-tool turn cannot balloon the prompt. Applied across
# tool results only; documents have their own small per-chunk budget.
_TOOL_TOTAL_CHAR_BUDGET = 14000
_MAX_DOCS = 6
_MAX_TOOL_RESULTS = 8

EVIDENCE_DOC = "doc"
EVIDENCE_TOOL = "tool"


def _serialize_tool_result(call: dict[str, Any]) -> str:
    """Render one executed tool call as evidence, successes and failures alike.

    Failures are included deliberately: an answer claiming an action succeeded
    when its tool result says otherwise is precisely the fabrication this
    validator should catch, and it can only catch it if it can see the failure.
    """
    result = call.get("result")
    if not isinstance(result, dict):
        result = {"value": result}

    success = result.get("success")
    status = "SUCCESS" if success else ("FAILED" if success is not None else "UNKNOWN")

    payload: dict[str, Any] = {
        key: value
        for key, value in result.items()
        if key not in {"success"} and value is not None
    }
    try:
        body = json.dumps(payload, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        body = str(payload)

    if len(body) > _TOOL_CHAR_BUDGET:
        body = (
            body[:_TOOL_CHAR_BUDGET]
            + f"... [TRUNCATED — {len(body)} chars total, remainder not shown]"
        )
    return f"{status} {body}"


def build_evidence(
    retrieved_context: list[dict[str, Any]] | None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Unify retrieved chunks and executed tool results into one evidence list.

    Agent-mode answers are frequently derived from tools rather than from RAG.
    Judging those against RAG chunks alone measured at 3 of 3 correct answers
    rejected in production (docs/delivery/grounding-validator-latency.json) —
    a HubSpot search result was called unsupported because five unrelated
    knowledge snippets did not mention it. Tool results are the missing half of
    the evidence, not a second-class hint.
    """
    evidence: list[dict[str, Any]] = []

    for chunk in retrieved_context or []:
        if not isinstance(chunk, dict):
            continue
        content = str(chunk.get("content") or chunk.get("snippet") or "").strip()
        if not content:
            continue
        evidence.append(
            {
                "kind": EVIDENCE_DOC,
                "label": str(chunk.get("source") or chunk.get("title") or "document"),
                "content": content[:_DOC_CHAR_BUDGET],
            }
        )

    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        tool = str(call.get("tool") or "").strip()
        if not tool:
            continue
        evidence.append(
            {
                "kind": EVIDENCE_TOOL,
                "label": tool,
                "content": _serialize_tool_result(call),
            }
        )

    return evidence


def _evidence_block(evidence: list[dict[str, Any]]) -> str:
    docs = [item for item in evidence if item.get("kind") == EVIDENCE_DOC][:_MAX_DOCS]
    tools = [item for item in evidence if item.get("kind") == EVIDENCE_TOOL][
        :_MAX_TOOL_RESULTS
    ]

    lines: list[str] = []
    spent = 0
    for index, item in enumerate(tools, start=1):
        content = str(item["content"])
        remaining = _TOOL_TOTAL_CHAR_BUDGET - spent
        if remaining <= 0:
            lines.append(f"[tool {index}] {item['label']} -> [OMITTED — prompt budget]")
            continue
        if len(content) > remaining:
            content = content[:remaining] + "... [TRUNCATED — prompt budget]"
        spent += len(content)
        lines.append(f"[tool {index}] {item['label']} -> {content}")
    for index, item in enumerate(docs, start=1):
        lines.append(f"[doc {index}] {item['label']}: {item['content']}")
    return "\n".join(lines) or "(no evidence)"


async def validate_grounded_answer(
    answer: str,
    retrieved_context: list[dict[str, Any]],
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    confidence_threshold: float = 0.4,
    org_id: str | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """
    Check whether answer claims trace to the turn's evidence using a fast model call.

    Evidence is retrieved context AND the tool results produced this turn. Returns
    {is_valid, issues, requires_human, confidence}.
    """
    text = (answer or "").strip()
    if not text:
        return {
            "is_valid": False,
            "issues": ["empty_answer"],
            "requires_human": True,
            **label_confidence(0.0, source=CONFIDENCE_SOURCE_INSUFFICIENT, is_estimate=False),
        }

    evidence = build_evidence(retrieved_context, tool_calls)
    truncated = any("[TRUNCATED" in str(item.get("content") or "") for item in evidence)
    if not evidence:
        return {
            "is_valid": False,
            "issues": ["no_retrieved_context"],
            "requires_human": True,
            **label_confidence(0.1, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
        }

    prompt = (
        "You are a grounding validator. Decide if the ANSWER is supported by EVIDENCE.\n\n"
        "EVIDENCE comes in two kinds:\n"
        "  [tool N] a tool the assistant actually executed this turn, and its result\n"
        "  [doc N]  a retrieved document chunk\n\n"
        "Tool results are authoritative primary evidence. If the answer restates, "
        "counts, filters, summarizes or reformats data present in a tool result, it "
        "IS grounded — it does not also need document support.\n\n"
        "Flag ONLY:\n"
        "  - factual claims traceable to neither tool results nor documents\n"
        "  - invented entities, names, or identifiers\n"
        "  - numbers that contradict the evidence or appear nowhere in it\n"
        "  - claims that an action succeeded when its tool result shows FAILED\n\n"
        "Do NOT flag: conversational framing, offers to help further, restatements "
        "of the user's own question, formatting choices, or an honest report that "
        "no results were found when a tool returned none.\n\n"
        "TRUNCATION: a tool result may end with [TRUNCATED ...]. That evidence is "
        "incomplete, not contradictory. If the answer names records of the same "
        "kind the tool returned, treat them as plausibly present in the omitted "
        "remainder and do NOT flag them as unsupported. Only flag a claim against "
        "a truncated result if the visible portion actively contradicts it.\n\n"
        f"EVIDENCE:\n{_evidence_block(evidence)}\n\n"
        f"ANSWER:\n{text[:4000]}\n\n"
        'Respond JSON only: {"is_valid": true/false, "issues": ["..."], "confidence": 0.0-1.0, '
        '"requires_human": true/false}'
    )
    # Why this reason is tracked and returned. This function fails OPEN: any
    # problem lands on the permissive default below, which reports is_valid=True
    # with a heuristic confidence. Failing open is the right call for a
    # safety check on the user-facing path — a model hiccup should not turn a
    # correct answer into an apology — but a fail-open that does not SAY it
    # failed open is indistinguishable from a validator that works, which is the
    # exact silent-failure class this program has been closing all along. The
    # first live run of the tool-aware validator recorded assessorRan=false on
    # 3 of 3 verdicts and there was no way to tell whether the call raised or
    # the response simply did not parse. Now there is.
    fallthrough_reason = "unknown"
    try:
        router = get_model_router()
        response = await router.complete(
            task_type=TaskType.CLASSIFICATION,
            prompt=prompt,
            system_prompt="Validate grounding strictly. JSON only.",
            org_id=org_id,
            temperature=0.0,
            max_tokens=300,
        )
        raw = response.content or ""
        match = _JSON_BLOCK.search(raw)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception as exc:  # noqa: BLE001
                parsed = None
                fallthrough_reason = f"json_decode_error:{type(exc).__name__}"
                logger.warning(
                    "answer validation unparseable org_id=%s raw=%r", org_id, raw[:200]
                )
            if parsed is not None:
                confidence = float(parsed.get("confidence") or 0.0)
                is_valid = bool(parsed.get("is_valid")) and confidence >= confidence_threshold
                return {
                    "is_valid": is_valid,
                    "issues": list(parsed.get("issues") or []),
                    "requires_human": bool(parsed.get("requires_human")) or not is_valid,
                    "validator_fallthrough": None,
                    "evidence_truncated": truncated,
                    **label_confidence(
                        max(0.0, min(1.0, confidence)),
                        source=CONFIDENCE_SOURCE_MODEL,
                        is_estimate=True,
                    ),
                }
        else:
            fallthrough_reason = "no_json_in_response" if raw.strip() else "empty_response"
            logger.warning(
                "answer validation no-json org_id=%s raw=%r", org_id, raw[:200]
            )
    except Exception as exc:  # noqa: BLE001
        fallthrough_reason = f"model_error:{type(exc).__name__}"
        logger.warning("answer validation skipped org_id=%s error=%s", org_id, exc)

    return {
        "is_valid": True,
        "issues": [],
        "requires_human": False,
        "validator_fallthrough": fallthrough_reason,
        "evidence_truncated": truncated,
        **label_confidence(0.5, source=CONFIDENCE_SOURCE_HEURISTIC, is_estimate=True),
    }
