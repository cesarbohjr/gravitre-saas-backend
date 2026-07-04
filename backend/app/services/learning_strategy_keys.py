"""Shared strategy key builders for intelligence routing and learning."""
from __future__ import annotations

from typing import Any

from app.services.domain_intelligence_service import DOMAIN_CONFIDENCE_THRESHOLD


def domain_segment_active(classification: dict[str, Any] | None) -> bool:
    domain = (classification or {}).get("domain") or {}
    if domain.get("routing_active") is False:
        return False
    if domain.get("routing_active") is True:
        return True
    return float(domain.get("confidence") or 0) >= DOMAIN_CONFIDENCE_THRESHOLD


def _domain_parts(classification: dict[str, Any] | None, department: str | None = None) -> tuple[str, str, str, str]:
    cls = classification or {}
    domain = cls.get("domain") or {}
    industry = str(domain.get("industry_key") or domain.get("industry") or "default").lower()
    dept = str(
        department
        or domain.get("department_key")
        or domain.get("department")
        or cls.get("department")
        or cls.get("entity_type")
        or "default"
    ).lower()
    subdomain = str(domain.get("subdomain_key") or domain.get("subdomain") or "general").lower()
    task = str(cls.get("intent") or cls.get("task_type") or "general").lower()
    return industry, dept, subdomain, task


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
    domain_suffix = ""
    if domain_segment_active(cls):
        industry, dept, subdomain, _task = _domain_parts(cls)
        domain_suffix = f":{industry}:{dept}:{subdomain}"
    return f"route:{intent}:{model_part}:{graph}:{prediction}:{causal}:{web}{domain_suffix}"


def build_model_strategy_key(model_name: str) -> str:
    return f"model:{model_name}"


def parse_base_segment_key(classification: dict[str, Any] | None, department: str | None = None) -> str:
    cls = classification or {}
    if domain_segment_active(cls):
        industry, dept, subdomain, task = _domain_parts(cls, department)
        return f"{industry}:{dept}:{subdomain}:{task}"
    dept = department or cls.get("department") or cls.get("entity_type") or "default"
    task = cls.get("intent") or cls.get("task_type") or "general"
    return f"{dept}:{task}"


def build_cluster_segment_key(
    query_cluster_id: str,
    classification: dict[str, Any] | None = None,
    department: str | None = None,
) -> str:
    base = parse_base_segment_key(classification, department)
    return f"cluster:{query_cluster_id}:{base}"


def is_cluster_segment(segment_key: str) -> bool:
    return str(segment_key or "").startswith("cluster:")


def parse_cluster_id_from_segment(segment_key: str) -> str | None:
    if not is_cluster_segment(segment_key):
        return None
    parts = str(segment_key).split(":", 2)
    return parts[1] if len(parts) >= 2 and parts[1] else None


def parse_base_segment_key_from_segment(segment_key: str) -> str:
    if is_cluster_segment(segment_key):
        parts = str(segment_key).split(":", 2)
        if len(parts) >= 3 and parts[2]:
            return parts[2]
    return str(segment_key or "default")


def parse_segment_key(classification: dict[str, Any] | None, department: str | None = None) -> str:
    cls = classification or {}
    cluster_id = cls.get("query_cluster_id")
    if cluster_id:
        return build_cluster_segment_key(str(cluster_id), cls, department)
    return parse_base_segment_key(cls, department)
