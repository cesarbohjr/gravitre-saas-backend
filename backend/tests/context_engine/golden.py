"""Prompt output of the active engine for the harness cases, for byte-for-byte comparison.

``golden_flags_off.json`` was generated from origin/main (bbd331631, and again,
unchanged, at 44751167e), before the 3.0 Plus inputs, liveness and freshness
flags existed, with ``python -m tests.context_engine.golden write``. The test compares today's output
with every new flag at its default against it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tests.context_engine import harness as h

GOLDEN_PATH = Path(__file__).with_name("golden_flags_off.json")
RANKING_KEYS = (
    "mode",
    "candidateCount",
    "selectedCount",
    "duplicateCount",
    "tokenBudget",
    "evidenceTokenBudget",
    "tokensUsed",
    "selectedSourceIds",
    "excludedSources",
    "legacyPromptChars",
    "rankedPromptChars",
)


def engine_profile_snapshot() -> dict[str, Any]:
    """The classical path's use of the engine (prepare_assistant_turn): rank and render."""
    from app.services.context_prioritization_engine import (
        ContextSource,
        evidence_rows_to_context_sources,
        get_context_prioritization_engine,
        render_context_sources,
    )

    rows = [
        {"kind": "rag", "content": d["content"], "score": 0.7, "source": d["title"], "document_id": d["id"]}
        for d in h.DOCUMENTS
        if d["org_id"] == h.ORG_A
    ]
    sources = evidence_rows_to_context_sources(rows, query="What is the Pro plan list price?")
    sources.append(ContextSource("org_context", "org_context", "Organization snapshot", 0.0, "Northwind, 40 staff"))
    sources.append(ContextSource("conversation_memory", "conversation_memory", "Conversation memory", 0.0, "User asked about pricing"))
    profile = get_context_prioritization_engine().build_context_profile(
        raw_sources=sources,
        classification={"intent": "knowledge_lookup", "department": "sales"},
        token_budget=400,
    )
    return {
        "rendered": render_context_sources(profile.ranked_sources),
        "explanation": profile.to_explanation_dict(),
    }


def snapshot(**overrides: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mode in ("shadow", "active"):
        for surface, spoken in (("chat", False), ("voice", True)):
            results: dict[str, Any] = {}
            import asyncio
            from contextlib import ExitStack

            async def _go(mode: str = mode, spoken: bool = spoken, results: dict[str, Any] = results) -> None:
                with ExitStack() as stack:
                    h._patches(stack)
                    for case in h.CASES:
                        block, meta = await h.build(case, h.settings_for(mode, **overrides), spoken=spoken)
                        ranking = meta.get("contextRanking") or {}
                        results[case.key] = {
                            "block": block,
                            "ranking": {k: ranking.get(k) for k in RANKING_KEYS},
                            "meta_keys": sorted(meta.keys()),
                            "ranking_keys": sorted(ranking.keys()),
                        }

            asyncio.run(_go())
            out[f"{mode}/{surface}"] = results
    out["engine_profile"] = engine_profile_snapshot()
    return out


def main() -> None:
    if sys.argv[1:] == ["write"]:
        GOLDEN_PATH.write_text(json.dumps(snapshot(), indent=1, sort_keys=True, default=str) + "\n")
        print(f"wrote {GOLDEN_PATH}")
    else:
        print(json.dumps(snapshot(), indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
