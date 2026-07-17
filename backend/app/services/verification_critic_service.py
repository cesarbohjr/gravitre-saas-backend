"""Pre-delivery verification critics (Tier 2).

Lightweight review pass before answers leave the assistant — connector, business,
and write-scope checks using a fast model tier.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.assistant_routing_tier import model_for_routing_phase
from app.services.model_router import TaskType, get_model_router

logger = get_logger(__name__)

_JSON_BLOCK = re.compile(r"\{[^{}]*\}", re.DOTALL)


class VerificationCriticService:
    """Runs a fast critic pass on assistant answers before delivery."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def verify_before_delivery(
        self,
        *,
        query: str,
        answer: str,
        classification: dict[str, Any],
        routing_tier: str = "multi_step",
        rag_sources: list[dict[str, Any]] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        text = (answer or "").strip()
        if not text or len(text) < 40:
            return {"passed": True, "issues": [], "revised_answer": answer, "skipped": "short_answer"}

        requires_action = bool(classification.get("requires_action"))
        tool_results = tool_results or []
        failed_tools = [
            row for row in tool_results if isinstance(row, dict) and row.get("success") is False
        ]
        if failed_tools and not requires_action:
            return {
                "passed": False,
                "issues": ["connector_tool_failed"],
                "revised_answer": answer,
                "critic": "connector",
            }

        # Heuristic connector critic — empty structured results after tool use.
        if tool_results and requires_action:
            successes = [r for r in tool_results if r.get("success")]
            if not successes:
                return {
                    "passed": False,
                    "issues": ["no_successful_connector_results"],
                    "revised_answer": answer,
                    "critic": "connector",
                }

        model = model_for_routing_phase("verification", routing_tier)
        context_lines = []
        for idx, src in enumerate((rag_sources or [])[:4], start=1):
            snippet = str(src.get("content") or src.get("snippet") or "")[:400]
            if snippet:
                context_lines.append(f"[{idx}] {snippet}")
        context_block = "\n".join(context_lines) or "(no retrieved context)"

        prompt = (
            "You are a delivery critic for an enterprise AI operator. "
            "Review the draft answer for obvious issues: unsupported claims, missing caveats when "
            "tools failed, raw JSON, or answering without evidence when context is thin.\n"
            f"User question:\n{query[:1200]}\n\n"
            f"Retrieved context:\n{context_block}\n\n"
            f"Draft answer:\n{text[:3500]}\n\n"
            'Return JSON only: {"passed": bool, "issues": [str], "revised_answer": str|null}. '
            "If passed, revised_answer may be null. Keep revisions minimal."
        )
        try:
            router = get_model_router(self.settings)
            response = await router.complete(
                TaskType.SUMMARIZATION,
                prompt,
                org_id=org_id,
                model_override=model,
                max_tokens=500,
            )
            raw = str(response.content or "").strip()
            match = _JSON_BLOCK.search(raw)
            if not match:
                return {"passed": True, "issues": [], "revised_answer": answer, "skipped": "unparseable"}
            parsed = json.loads(match.group(0))
            passed = bool(parsed.get("passed", True))
            issues = [str(i) for i in (parsed.get("issues") or []) if i]
            revised = parsed.get("revised_answer")
            if isinstance(revised, str) and revised.strip() and not passed:
                return {
                    "passed": False,
                    "issues": issues or ["critic_revision"],
                    "revised_answer": revised.strip(),
                    "critic": "business",
                }
            return {"passed": passed, "issues": issues, "revised_answer": answer, "critic": "business"}
        except Exception as exc:  # noqa: BLE001
            logger.debug("verification_critic_skipped org_id=%s error=%s", org_id, exc)
            return {"passed": True, "issues": [], "revised_answer": answer, "skipped": "error"}


_service: VerificationCriticService | None = None


def get_verification_critic_service(settings: Settings | None = None) -> VerificationCriticService:
    global _service
    if _service is None or settings is not None:
        _service = VerificationCriticService(settings)
    return _service
