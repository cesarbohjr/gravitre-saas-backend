"""Shared strategy key builders for intelligence routing and learning."""
from __future__ import annotations

from typing import Any


def build_route_strategy_key(
    model_selection: dict[str, Any] | None,
    classification: dict[str, Any] | None,
    enrichments: dict[str, Any] | None = None,
) -> str:
    selection = model_selection or {}
    cls = classification or {}
    enrich = enrichments or {}
    if selection.get("primary_model") == "ml_internal":
        model_part = f"ml:{selection.get('ml_model_name') or 'internal'}"
    else:
        model_part = f"llm:{selection.get('llm_tier') or selection.get('fallback') or 'standard'}"
    intent = str(cls.get("intent") or "unknown")
    graph = "graph" if enrich.get("graph") else "no_graph"
    prediction = "pred" if enrich.get("prediction") else "no_pred"
    causal = "causal" if enrich.get("causal") else "no_causal"
    web = "web" if enrich.get("web") else "no_web"
    return f"route:{intent}:{model_part}:{graph}:{prediction}:{causal}:{web}"


def build_model_strategy_key(model_name: str) -> str:
    return f"model:{model_name}"


def parse_segment_key(classification: dict[str, Any] | None, department: str | None = None) -> str:
    cls = classification or {}
    dept = department or cls.get("department") or cls.get("entity_type") or "default"
    task = cls.get("intent") or cls.get("task_type") or "general"
    return f"{dept}:{task}"
