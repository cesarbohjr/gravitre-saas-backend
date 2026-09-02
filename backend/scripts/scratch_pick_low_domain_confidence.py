"""Which messages actually fall below DOMAIN_CONFIDENCE_THRESHOLD?

Site 10's LLM tier only runs when rule + org-profile confidence lands under 0.55.
The first live attempt used business-flavoured messages that scored 0.7-0.8 on
keywords alone, so the tier was never reached and proved nothing.

Rather than guess again, score candidates against the real rule classifier and
keep only the ones that genuinely leave the rules uncertain.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

for _k, _v in load_env().items():
    os.environ.setdefault(_k, _v)

CANDIDATES = [
    "the thing we talked about before still feels unresolved and i would like to get "
    "to the bottom of it sometime this week",
    "there is a pattern here that keeps coming back around again and i want to really "
    "understand why it happens at all",
    "something about the way this is set up right now bothers me and i cannot quite "
    "put my finger on what it actually is",
    "walk me through how you would think about this from first principles without "
    "assuming any of the usual constraints apply here",
    "we keep going back and forth on this one and i would rather settle it properly "
    "than keep revisiting it every single time",
]


def main() -> int:
    from app.services.contextual_understanding_service import ContextualUnderstandingService
    from app.services.domain_intelligence_service import (
        DOMAIN_CONFIDENCE_THRESHOLD,
        DomainIntelligenceService,
    )

    dom = DomainIntelligenceService()
    print(f"threshold: {DOMAIN_CONFIDENCE_THRESHOLD}\n")
    good: list[str] = []
    for text in CANDIDATES:
        rules = dom._classify_by_rules(text, {}, understanding=None)
        conf = float(rules.get("confidence") or 0)
        reaches_llm = conf < DOMAIN_CONFIDENCE_THRESHOLD
        rule_goal = ContextualUnderstandingService._can_infer_goal_from_rules(text)
        site9 = (not rule_goal) and len(text.split()) > 8
        ok = reaches_llm and site9
        if ok:
            good.append(text)
        print(
            f"  conf={conf:5.3f} reachesLLM={reaches_llm!s:5s} site9={site9!s:5s} "
            f"dept={rules.get('department')} :: {text[:60]}..."
        )

    print(f"\nusable for site 10: {len(good)}/{len(CANDIDATES)}")
    for g in good[:3]:
        print(f"  - {g}")
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
