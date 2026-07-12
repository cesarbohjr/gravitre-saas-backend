"""Measured Knowledge Phase 2 rerank evaluation (STA-313).

Compares baseline ms-marco cross-encoder against optional candidates
(bge / Cohere). Does **not** change production defaults — upgrade only
when docs/delivery artifacts show a measured win.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.config import Settings
from app.rag.hybrid_rerank import (
    _cross_encoder_rerank,
    _lexical_rerank,
    reset_cross_encoder_cache,
)

RerankFn = Callable[[str, list[dict[str, Any]], int], tuple[list[dict[str, Any]], str]]


@dataclass(frozen=True)
class EvalQuery:
    id: str
    query: str
    relevant_ids: frozenset[str]


def load_eval_bundle(path: Path) -> tuple[list[EvalQuery], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = [
        EvalQuery(
            id=str(item["id"]),
            query=str(item["query"]),
            relevant_ids=frozenset(str(x) for x in item.get("relevant_ids") or []),
        )
        for item in data.get("queries") or []
    ]
    corpus = [
        {
            "id": str(row["id"]),
            "title": str(row.get("title") or ""),
            "content": str(row.get("content") or ""),
            "score": 0.0,
        }
        for row in data.get("corpus") or []
    ]
    return queries, corpus


def precision_at_k(ranked_ids: list[str], relevant: frozenset[str], k: int) -> float:
    if k <= 0 or not relevant:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for doc_id in top if doc_id in relevant)
    return hits / float(min(k, len(relevant)))


def mrr(ranked_ids: list[str], relevant: frozenset[str]) -> float:
    for idx, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / float(idx)
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / float(len(values)) if values else 0.0


def make_cross_encoder_reranker(model_name: str, settings: Settings) -> RerankFn:
    def _rerank(
        query: str,
        rows: list[dict[str, Any]],
        top_k: int,
    ) -> tuple[list[dict[str, Any]], str]:
        reset_cross_encoder_cache()
        patched = settings.model_copy(
            update={
                "rag_cross_encoder_model": model_name,
                "rag_cross_encoder_enabled": True,
                "rag_disable_cross_encoder": False,
                # Eval scores absolute ranks; do not drop candidates below prod threshold.
                "rag_rerank_score_threshold": -1.0e9,
            }
        )
        ranked, method = _cross_encoder_rerank(query, rows, top_k=top_k, settings=patched)
        if not ranked:
            ranked = _lexical_rerank(query, rows, top_k=top_k)
            return ranked, f"{method}+lexical_fallback"
        return ranked, method

    return _rerank


def make_lexical_reranker() -> RerankFn:
    def _rerank(
        query: str,
        rows: list[dict[str, Any]],
        top_k: int,
    ) -> tuple[list[dict[str, Any]], str]:
        return _lexical_rerank(query, rows, top_k=top_k), "lexical_overlap"

    return _rerank


def make_cohere_reranker(api_key: str, model: str = "rerank-english-v3.0") -> RerankFn:
    def _rerank(
        query: str,
        rows: list[dict[str, Any]],
        top_k: int,
    ) -> tuple[list[dict[str, Any]], str]:
        payload = {
            "model": model,
            "query": query,
            "documents": [str(row.get("content") or "") for row in rows],
            "top_n": min(top_k, len(rows)),
        }
        req = urllib.request.Request(
            "https://api.cohere.com/v1/rerank",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"cohere_rerank_http_{exc.code}: {detail[:240]}") from exc

        results = body.get("results") or []
        ranked: list[dict[str, Any]] = []
        for item in results:
            idx = int(item.get("index"))
            row = dict(rows[idx])
            row["score"] = float(item.get("relevance_score") or 0.0)
            ranked.append(row)
        return ranked[:top_k], f"cohere:{model}"

    return _rerank


def evaluate_reranker(
    name: str,
    rerank: RerankFn,
    queries: list[EvalQuery],
    corpus: list[dict[str, Any]],
    *,
    top_k: int = 3,
) -> dict[str, Any]:
    per_query: list[dict[str, Any]] = []
    p_at_k: list[float] = []
    mrr_scores: list[float] = []
    methods: set[str] = set()
    error: str | None = None

    for item in queries:
        try:
            ranked, method = rerank(item.query, [dict(row) for row in corpus], top_k)
            methods.add(method)
            ranked_ids = [str(row.get("id") or "") for row in ranked]
            p = precision_at_k(ranked_ids, item.relevant_ids, top_k)
            r = mrr(ranked_ids, item.relevant_ids)
            p_at_k.append(p)
            mrr_scores.append(r)
            per_query.append(
                {
                    "id": item.id,
                    "precision_at_k": round(p, 4),
                    "mrr": round(r, 4),
                    "ranked_ids": ranked_ids,
                    "method": method,
                }
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            per_query.append(
                {
                    "id": item.id,
                    "error": error,
                }
            )
            break

    degraded = any(
        "unavailable" in m or "load_failed" in m or "predict_failed" in m for m in methods
    )
    status = "error" if error else ("degraded" if degraded else "ok")
    return {
        "name": name,
        "status": status,
        "error": error,
        "n_queries_scored": len(p_at_k),
        "top_k": top_k,
        "mean_precision_at_k": round(mean(p_at_k), 4),
        "mean_mrr": round(mean(mrr_scores), 4),
        "methods": sorted(methods),
        "per_query": per_query,
        "note": (
            "Cross-encoder weights unavailable in this environment; scores used lexical fallback and are not an upgrade decision."
            if degraded
            else None
        ),
    }


def compare_results(baseline: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    recommendations: list[str] = []
    if baseline.get("status") != "ok":
        recommendations.append(
            "Baseline not fully scored (error or degraded fallback) — do not change production reranker."
        )
        return {"upgrade_authorized": False, "recommendations": recommendations}

    base_p = float(baseline.get("mean_precision_at_k") or 0.0)
    base_mrr = float(baseline.get("mean_mrr") or 0.0)
    winners: list[str] = []

    for candidate in candidates:
        if candidate.get("status") != "ok":
            recommendations.append(
                f"{candidate.get('name')}: not scored ({candidate.get('error') or 'unavailable'})"
            )
            continue
        cand_p = float(candidate.get("mean_precision_at_k") or 0.0)
        cand_mrr = float(candidate.get("mean_mrr") or 0.0)
        delta_p = round(cand_p - base_p, 4)
        delta_mrr = round(cand_mrr - base_mrr, 4)
        candidate["delta_precision_at_k"] = delta_p
        candidate["delta_mrr"] = delta_mrr
        # Require a clear precision win; MRR tie-break only when precision ties.
        if cand_p > base_p + 0.02 or (cand_p >= base_p and cand_mrr > base_mrr + 0.02):
            winners.append(str(candidate.get("name")))
            recommendations.append(
                f"{candidate.get('name')}: measured win (delta_P@{baseline.get('top_k')}={delta_p}, delta_MRR={delta_mrr})"
            )
        else:
            recommendations.append(
                f"{candidate.get('name')}: no measured win (delta_P@{baseline.get('top_k')}={delta_p}, delta_MRR={delta_mrr}) — keep ms-marco"
            )

    return {
        "upgrade_authorized": bool(winners),
        "winners": winners,
        "recommendations": recommendations,
        "note": "Production default must stay ms-marco unless upgrade_authorized and a human ships an explicit change.",
    }


def default_settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        rag_cross_encoder_enabled=True,
        rag_disable_cross_encoder=False,
    )


def build_rerankers(
    settings: Settings,
    *,
    include_heavy: bool = False,
    cohere_api_key: str | None = None,
) -> list[tuple[str, RerankFn]]:
    rerankers: list[tuple[str, RerankFn]] = [
        ("lexical_overlap", make_lexical_reranker()),
        (
            "ms-marco-MiniLM-L-6-v2",
            make_cross_encoder_reranker("cross-encoder/ms-marco-MiniLM-L-6-v2", settings),
        ),
    ]
    if include_heavy:
        rerankers.append(
            (
                "bge-reranker-base",
                make_cross_encoder_reranker("BAAI/bge-reranker-base", settings),
            )
        )
        rerankers.append(
            (
                "bge-reranker-large",
                make_cross_encoder_reranker("BAAI/bge-reranker-large", settings),
            )
        )
    key = (cohere_api_key or os.environ.get("COHERE_API_KEY") or "").strip()
    if key:
        rerankers.append(("cohere-rerank-english-v3.0", make_cohere_reranker(key)))
    return rerankers
