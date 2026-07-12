"""STA-313 Knowledge Phase 2: measured rerank eval harness.

Usage (from repo root, with backend venv):
  python scripts/eval-knowledge-rerank.py
  python scripts/eval-knowledge-rerank.py --include-heavy   # bge-base/large (downloads models)
  python scripts/eval-knowledge-rerank.py --cohere          # requires COHERE_API_KEY

Does not change production reranker settings.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.rerank_eval import (  # noqa: E402
    build_rerankers,
    compare_results,
    default_settings,
    evaluate_reranker,
    load_eval_bundle,
)

DEFAULT_QUERIES = REPO / "docs" / "delivery" / "sta313-rerank-eval-queries.json"
DEFAULT_OUT = REPO / "docs" / "delivery" / "sta313-rerank-eval-results.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="STA-313 Knowledge rerank measured eval")
    parser.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--include-heavy",
        action="store_true",
        help="Also score BAAI/bge-reranker-base and bge-reranker-large (model download)",
    )
    parser.add_argument(
        "--cohere",
        action="store_true",
        help="Include Cohere Rerank when COHERE_API_KEY is set",
    )
    parser.add_argument(
        "--skip-cross-encoder",
        action="store_true",
        help="Score lexical only (CI smoke without sentence_transformers weights)",
    )
    args = parser.parse_args()

    queries, corpus = load_eval_bundle(args.queries)
    settings = default_settings()
    rerankers = build_rerankers(
        settings,
        include_heavy=args.include_heavy,
        cohere_api_key=(None if args.cohere else ""),
    )
    if args.skip_cross_encoder:
        rerankers = [item for item in rerankers if item[0] == "lexical_overlap"]
    elif not args.cohere:
        rerankers = [item for item in rerankers if not str(item[0]).startswith("cohere-")]

    results: list[dict] = []
    for name, fn in rerankers:
        print(f"scoring {name} …", flush=True)
        results.append(evaluate_reranker(name, fn, queries, corpus, top_k=args.top_k))

    baseline = next((r for r in results if r["name"] == "ms-marco-MiniLM-L-6-v2"), None)
    if baseline is None and results:
        baseline = results[0]
    candidates = [r for r in results if r is not baseline]
    comparison = compare_results(baseline or {"status": "error"}, candidates)

    report = {
        "ticket": "STA-313",
        "title": "Knowledge Phase 2 measured rerank eval",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "queries_path": str(args.queries.as_posix()),
        "n_queries": len(queries),
        "n_corpus": len(corpus),
        "top_k": args.top_k,
        "baseline": baseline,
        "candidates": candidates,
        "comparison": comparison,
        "production_default_unchanged": True,
        "verdict": (
            "UPGRADE_CANDIDATE"
            if comparison.get("upgrade_authorized")
            else "KEEP_MS_MARCO"
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "out": str(args.out)}, indent=2))
    for line in comparison.get("recommendations") or []:
        print(f"- {line}")
    return 0 if (baseline or {}).get("status") in {"ok", "degraded"} or args.skip_cross_encoder else 1


if __name__ == "__main__":
    raise SystemExit(main())
