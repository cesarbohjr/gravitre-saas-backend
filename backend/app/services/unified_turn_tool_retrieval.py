"""Embedding-based tool retrieval for unified-turn task-shaped calls.

Phase 0 chose keyword ``narrow_tools_for_turn`` first; this module adds semantic
top-k over the same connected tool set for task/mixed turns only. Social turns
keep keyword narrowing. Fail-closed to keyword on embedding errors.

Does not skip the reasoning call — only selects which tool schemas are attached.
"""
from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.agent_platform_optimizer import (
    compress_tool_definitions,
    narrow_tools_for_turn,
    _is_platform_tool,
    _is_write_tool,
    _mentioned_connectors,
    _tool_integration,
    _tool_name,
    _WRITE_TOOL_HINT,
)

logger = get_logger(__name__)

_CACHE_LOCK = threading.Lock()
# key: f"{model}:{name}:{doc_hash}" -> embedding vector
_TOOL_EMBED_CACHE: dict[str, list[float]] = {}


def _tool_document(tool: dict[str, Any]) -> str:
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else {}
    name = str(fn.get("name") or tool.get("name") or "")
    desc = str(fn.get("description") or tool.get("description") or "")
    invoke = str(tool.get("invoke_action") or "")
    integration = _tool_integration(tool)
    parts = [name.replace("_", " "), integration, desc]
    if invoke:
        parts.append(invoke.replace(".", " "))
    return " | ".join(p.strip() for p in parts if p and str(p).strip())


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return -1.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _cache_key(model: str, name: str, doc: str) -> str:
    return f"{model}:{name}:{hash(doc)}"


def _embed_tools(
    tools: list[dict[str, Any]],
    *,
    settings: Settings,
    org_id: str | None,
    stats_out: dict[str, Any] | None = None,
) -> list[tuple[dict[str, Any], list[float]]]:
    from app.rag.embedding import embed_texts_batch_openai

    model = str(getattr(settings, "embedding_model", None) or "text-embedding-3-small")
    out: list[tuple[dict[str, Any], list[float]]] = []
    missing: list[tuple[dict[str, Any], str, str]] = []
    cache_hits = 0
    t_cache = time.perf_counter()
    with _CACHE_LOCK:
        for tool in tools:
            name = _tool_name(tool)
            doc = _tool_document(tool)
            key = _cache_key(model, name, doc)
            cached = _TOOL_EMBED_CACHE.get(key)
            if cached is not None:
                cache_hits += 1
                out.append((tool, cached))
            else:
                missing.append((tool, name, doc))
    cache_lookup_ms = int((time.perf_counter() - t_cache) * 1000)

    tool_docs_ms = 0
    batch_api_calls = 0
    if missing:
        t_batch = time.perf_counter()
        docs = [doc for _, _, doc in missing]
        vectors = embed_texts_batch_openai(docs, settings, org_id=org_id)
        tool_docs_ms = int((time.perf_counter() - t_batch) * 1000)
        batch_api_calls = 1
        with _CACHE_LOCK:
            for (tool, name, doc), vector in zip(missing, vectors, strict=True):
                key = _cache_key(model, name, doc)
                _TOOL_EMBED_CACHE[key] = vector
                out.append((tool, vector))

    if stats_out is not None:
        stats_out.update(
            {
                "embed_tool_doc_cache_hits": cache_hits,
                "embed_tool_doc_cache_misses": len(missing),
                "embed_tool_docs_ms": tool_docs_ms,
                "embed_tool_doc_batch_api_calls": batch_api_calls,
                "embed_tool_doc_cache_lookup_ms": cache_lookup_ms,
                "embed_tool_doc_vectors": len(out),
            }
        )
    return out


def embed_narrow_tools_for_turn(
    tools: list[dict[str, Any]],
    *,
    query: str,
    settings: Settings,
    org_id: str | None = None,
    connected_integrations: list[str] | None = None,
    classification: dict[str, Any] | None = None,
    requires_action: bool | None = None,
    max_tools: int = 16,
    max_per_connector: int = 8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Semantic top-k tool selection; falls back to keyword narrow on failure."""
    if not tools:
        return [], {
            "totalTools": 0,
            "visibleTools": 0,
            "retrievalMethod": "embedding_narrow_tools_for_turn",
            "embeddingToolRetrieval": True,
        }

    try:
        from app.rag.embedding import get_embedding_timed

        narrow_start = time.perf_counter()
        connected = [str(c).strip().lower() for c in (connected_integrations or []) if str(c).strip()]
        platform_tools = [t for t in tools if _is_platform_tool(t)]
        connector_tools = [t for t in tools if not _is_platform_tool(t)]

        focus = _mentioned_connectors(query, classification, connected)
        if not focus and connected:
            focus = set(connected[:3])

        action_required = (
            bool(requires_action)
            if requires_action is not None
            else bool((classification or {}).get("requires_action"))
            or bool(_WRITE_TOOL_HINT.search(query or ""))
        )

        candidates: list[dict[str, Any]] = []
        for tool in connector_tools:
            integration = _tool_integration(tool)
            if focus and integration not in focus and integration not in {"platform", "mcp", "browser"}:
                continue
            if not action_required and _is_write_tool(tool):
                continue
            candidates.append(tool)

        if action_required:
            for tool in connector_tools:
                if not _is_write_tool(tool):
                    continue
                integration = _tool_integration(tool)
                if focus and integration not in focus:
                    continue
                if tool not in candidates:
                    candidates.append(tool)

        if not candidates:
            candidates = list(connector_tools)

        query_text = (query or "").strip() or "task"
        tool_partial: dict[str, Any] = {}

        def _load_tool_vectors() -> list[tuple[dict[str, Any], list[float]]]:
            return _embed_tools(
                candidates,
                settings=settings,
                org_id=org_id,
                stats_out=tool_partial,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            query_future = pool.submit(get_embedding_timed, query_text, settings, org_id)
            tools_future = pool.submit(_load_tool_vectors)
            query_vec, query_ms = query_future.result()
            scored = tools_future.result()

        t_rank = time.perf_counter()
        ranked = sorted(
            ((_cosine(query_vec, vec), tool) for tool, vec in scored),
            key=lambda row: row[0],
            reverse=True,
        )

        selected: list[dict[str, Any]] = []
        per_connector: dict[str, int] = {}
        budget = max(1, int(max_tools) - len(platform_tools))
        for score, tool in ranked:
            if score < 0:
                continue
            integration = _tool_integration(tool)
            if per_connector.get(integration, 0) >= max_per_connector:
                continue
            selected.append(tool)
            per_connector[integration] = per_connector.get(integration, 0) + 1
            if len(selected) >= budget:
                break

        if len(selected) < 3 and len(candidates) > len(selected):
            for score, tool in ranked:
                if tool in selected:
                    continue
                selected.append(tool)
                if len(selected) >= min(budget, max(3, budget)):
                    break

        similarity_ms = int((time.perf_counter() - t_rank) * 1000)
        narrow_total_ms = int((time.perf_counter() - narrow_start) * 1000)

        visible = compress_tool_definitions(platform_tools + selected)
        stats = {
            "totalTools": len(tools),
            "visibleTools": len(visible),
            "focusedConnectors": sorted(focus),
            "actionRequired": action_required,
            "compressed": True,
            "retrievalMethod": "embedding_narrow_tools_for_turn",
            "embeddingToolRetrieval": True,
            "embeddingCandidateCount": len(candidates),
            "topSimilarity": round(float(ranked[0][0]), 4) if ranked else None,
            "embed_query_ms": query_ms,
            "embed_similarity_rank_ms": similarity_ms,
            "embed_narrow_total_ms": narrow_total_ms,
            **tool_partial,
        }
        return visible, stats
    except Exception as exc:  # noqa: BLE001
        logger.warning("embed_narrow_tools_for_turn failed; keyword fallback: %s", exc)
        visible, stats = narrow_tools_for_turn(
            tools,
            query=query,
            classification=classification,
            connected_integrations=connected_integrations,
            requires_action=requires_action,
            max_tools=max_tools,
            max_per_connector=max_per_connector,
        )
        stats = {
            **(stats or {}),
            "retrievalMethod": "keyword_narrow_tools_for_turn",
            "embeddingToolRetrieval": False,
            "embeddingFallbackReason": str(exc)[:240],
        }
        return visible, stats


def warm_tool_document_embeddings(*, settings: Settings | None = None) -> int:
    """Pre-embed catalog tool docs at process start (C path cold-start mitigation).

    Best-effort; no-op when embedding retrieval is disabled or OpenAI is unset.
    """
    active = settings or get_settings()
    if not bool(getattr(active, "unified_turn_embedding_tool_retrieval", True)):
        return 0
    if not (active.openai_api_key or "").strip():
        return 0
    try:
        from app.services.tool_registry import get_tool_registry

        registry = get_tool_registry()
        tools: list[dict[str, Any]] = []
        for name in registry.list_tool_names():
            spec = registry.get_spec(name)
            if spec is None:
                continue
            invoke = str(spec.invoke_action or "")
            if not registry._action_implemented(spec, invoke):  # noqa: SLF001
                continue
            tools.append(spec.to_openai_tool())
        if not tools:
            return 0
        partial: dict[str, Any] = {}
        _embed_tools(tools, settings=active, org_id=None, stats_out=partial)
        logger.info(
            "unified_turn_tool_doc_cache_warmed count=%s misses=%s batch_calls=%s",
            len(tools),
            partial.get("embed_tool_doc_cache_misses"),
            partial.get("embed_tool_doc_batch_api_calls"),
        )
        return len(tools)
    except Exception as exc:  # noqa: BLE001
        logger.warning("warm_tool_document_embeddings skipped: %s", exc)
        return 0


def is_task_shaped_for_retrieval(message: str) -> tuple[bool, str, str]:
    """Lightweight shape hint for retrieval/model tier only — never skips the reasoning call.

    Returns (use_embedding_path, shape_label, retrieval_query).
    Mixed → task portion for embedding query; conversational → keyword path.
    Ambiguous (None) → treat as task-shaped (fail closed to semantic retrieval).
    """
    from app.services.conversational_turn_gate import heuristic_turn_shape

    decision = heuristic_turn_shape(message)
    if decision is None:
        return True, "ambiguous_taskish", (message or "").strip()
    if decision.shape == "conversational":
        return False, "conversational", (message or "").strip()
    if decision.shape == "mixed":
        q = (decision.task_portion or message or "").strip()
        return True, "mixed", q
    return True, "task_shaped", (decision.task_portion or message or "").strip()
