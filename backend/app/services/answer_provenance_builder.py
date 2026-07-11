"""Wave 5 — calibrated uncertainty: label facts vs inferences vs assumptions."""
from __future__ import annotations

from typing import Any

from app.services.connector_session_state import inference_confidence_for_source


def collect_claims_from_sources(
    *,
    sources: list[dict[str, Any]] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
    inferred_fields: list[str] | None = None,
    inference_sources: dict[str, str] | None = None,
    memory_conflicts: list[Any] | None = None,
    answer_has_content: bool = True,
) -> list[dict[str, Any]]:
    """Build structured claims for trust/explainability envelopes."""
    claims: list[dict[str, Any]] = []

    for src in sources or []:
        if not isinstance(src, dict):
            continue
        title = str(src.get("source") or src.get("title") or "Knowledge source").strip()
        claims.append(
            {
                "text": title,
                "kind": "fact",
                "source": "retrieval",
                "confidence": "high",
            }
        )

    for tool in tool_results or []:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("displayName") or tool.get("name") or "tool").strip()
        output = tool.get("output") if isinstance(tool.get("output"), dict) else {}
        success = output.get("success")
        if success is False or tool.get("error"):
            continue
        if success is True or output:
            claims.append(
                {
                    "text": f"Tool result: {name}",
                    "kind": "fact",
                    "source": name,
                    "confidence": "high",
                }
            )

    for field in inferred_fields or []:
        src = str((inference_sources or {}).get(field) or "inference").strip()
        claims.append(
            {
                "text": f"Inferred {field} from {src}",
                "kind": "inference",
                "source": src,
                "confidence": inference_confidence_for_source(src),
            }
        )

    if memory_conflicts:
        claims.append(
            {
                "text": "Conflicting memories may affect this answer",
                "kind": "assumption",
                "source": "memory_conflicts",
                "confidence": "low",
            }
        )

    has_grounding = any(c["kind"] == "fact" for c in claims)
    if answer_has_content and not has_grounding and not (inferred_fields or []):
        claims.append(
            {
                "text": "Parts of this answer may be model inference without retrieved sources",
                "kind": "assumption",
                "source": "model",
                "confidence": "low",
            }
        )

    return claims[:20]


def assumption_strings(claims: list[dict[str, Any]]) -> list[str]:
    return [
        str(c.get("text") or "").strip()
        for c in claims
        if c.get("kind") in {"assumption", "inference"} and str(c.get("text") or "").strip()
    ]


def format_assumption_prefix(claims: list[dict[str, Any]]) -> str:
    """Short user-facing block labeling inferences/assumptions."""
    inferences = [c for c in claims if c.get("kind") == "inference"]
    assumptions = [c for c in claims if c.get("kind") == "assumption"]
    parts: list[str] = []
    if inferences:
        labels = "; ".join(str(c.get("text") or "") for c in inferences[:3] if c.get("text"))
        if labels:
            parts.append(f"I inferred: {labels}.")
    if assumptions:
        labels = "; ".join(str(c.get("text") or "") for c in assumptions[:2] if c.get("text"))
        if labels:
            parts.append(f"Note: {labels}.")
    return " ".join(parts).strip()


def claim_breakdown(claims: list[dict[str, Any]]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"facts": [], "inferences": [], "assumptions": []}
    for claim in claims:
        text = str(claim.get("text") or "").strip()
        if not text:
            continue
        kind = str(claim.get("kind") or "")
        if kind == "fact":
            buckets["facts"].append(text)
        elif kind == "inference":
            buckets["inferences"].append(text)
        elif kind == "assumption":
            buckets["assumptions"].append(text)
    return buckets
