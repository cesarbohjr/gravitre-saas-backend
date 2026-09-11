#!/usr/bin/env python3
"""Print real pass/fail rates for the adversarial NLU corpus. Not a green-gate."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "anon-test")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "service-role-test")
os.environ.setdefault("SUPABASE_JWT_SECRET", "jwt-test-secret-for-local-corpus")
sys.path.insert(0, str(ROOT / "backend"))

from app.services.cognitive_loop_controller import CognitiveLoopController
from app.services.cognitive_nlu_adversarial_corpus import (
    build_adversarial_nlu_corpus,
    corpus_stats,
)
from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway


async def main() -> int:
    items = build_adversarial_nlu_corpus()
    stats = corpus_stats(items)
    ctl = CognitiveLoopController()
    by_family: dict[str, Counter] = {}
    fails: list[dict] = []
    wrap_shortcut = 0
    wrap_n = 0

    for row in items:
        typed = await evaluate_intent_gateway(
            GatewayContext(message=row["message"], spoken_mode=False, org_id="org")
        )
        spoken = await evaluate_intent_gateway(
            GatewayContext(message=row["message"], spoken_mode=True, org_id="org")
        )
        family = row["family"]
        expected = row["expected"]
        typed_ok = typed.action == expected if expected in {"fallthrough", "shortcut"} else None
        spoken_ok = spoken.action == expected if expected in {"fallthrough", "shortcut"} else None
        pair_ok = typed.action == spoken.action
        fam = by_family.setdefault(family, Counter())
        fam["n"] += 1
        if expected == "fallthrough":
            if typed.action == "fallthrough" and spoken.action == "fallthrough":
                fam["pass"] += 1
                trace = ctl.begin(message=row["message"], spoken_mode=False)
                ctl.mark_perceive(trace, typed)
                if family in {"anchor", "vendor_job", "obscure", "multi_clause", "edge", "prioritize"}:
                    if trace.fast_path:
                        fails.append(
                            {
                                "id": row["id"],
                                "family": family,
                                "kind": "fast_path_on_operator",
                                "message": row["message"][:180],
                            }
                        )
                        fam["pass"] -= 1
                        fam["fail"] += 1
            else:
                fam["fail"] += 1
                fails.append(
                    {
                        "id": row["id"],
                        "family": family,
                        "kind": "expected_fallthrough",
                        "typed": f"{typed.action}:{typed.candidate_id}:{typed.reason}",
                        "spoken": f"{spoken.action}:{spoken.candidate_id}:{spoken.reason}",
                        "message": row["message"][:180],
                    }
                )
        elif family == "shortcut_seed":
            if typed.action == "shortcut" and spoken.action == "shortcut":
                fam["pass"] += 1
            else:
                fam["fail"] += 1
                fails.append(
                    {
                        "id": row["id"],
                        "family": family,
                        "kind": "expected_shortcut",
                        "typed": f"{typed.action}:{typed.candidate_id}",
                        "spoken": f"{spoken.action}:{spoken.candidate_id}",
                        "message": row["message"][:180],
                    }
                )
        else:
            wrap_n += 1
            if typed.action == "shortcut" and spoken.action == "shortcut":
                wrap_shortcut += 1
                fam["pass"] += 1
            else:
                fam["fail"] += 1
                fam.setdefault("report_not_shortcut", 0)
                fam["report_not_shortcut"] += 1
                fails.append(
                    {
                        "id": row["id"],
                        "family": family,
                        "kind": "social_or_wrap_not_shortcut",
                        "typed": f"{typed.action}:{typed.candidate_id}:{typed.reason}",
                        "spoken": f"{spoken.action}:{spoken.candidate_id}:{spoken.reason}",
                        "message": row["message"][:180],
                    }
                )
        if not pair_ok:
            fam["text_voice_mismatch"] += 1
            fails.append(
                {
                    "id": row["id"],
                    "family": family,
                    "kind": "text_voice_mismatch",
                    "typed": typed.action,
                    "spoken": spoken.action,
                    "message": row["message"][:180],
                }
            )

    fallthrough_n = sum(c["n"] for fam, c in by_family.items() if fam != "x")
    ft_n = sum(c["n"] for f, c in by_family.items() if f not in {"shortcut_seed", "social_report"})
    ft_pass = sum(c["pass"] for f, c in by_family.items() if f not in {"shortcut_seed", "social_report"})
    ft_fail = sum(c["fail"] for f, c in by_family.items() if f not in {"shortcut_seed", "social_report"})
    seed = by_family.get("shortcut_seed", Counter())
    social = by_family.get("social_report", Counter())

    out = {
        "total": stats["total"],
        "corpus_stats": stats,
        "fallthrough_families": {
            "n": ft_n,
            "pass": ft_pass,
            "fail": ft_fail,
            "rate": round(ft_pass / max(ft_n, 1), 4),
        },
        "shortcut_seeds": {
            "n": seed["n"],
            "pass": seed["pass"],
            "fail": seed["fail"],
            "rate": round(seed["pass"] / max(seed["n"], 1), 4),
        },
        "social_report": {
            "n": social["n"],
            "shortcut_both": social["pass"],
            "not_shortcut": social["fail"],
            "shortcut_rate": round(social["pass"] / max(social["n"], 1), 4),
            "note": "Reported honestly; not a 100% gate.",
        },
        "by_family": {k: dict(v) for k, v in sorted(by_family.items())},
        "fail_count": len(fails),
        "fails": fails[:80],
        "fail_kinds": dict(Counter(f["kind"] for f in fails)),
    }
    dest = ROOT / "docs" / "delivery" / "adversarial-nlu-corpus-current.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in out if k != "fails"}, indent=2))
    if fails:
        print("\nFAILS (first 40):")
        for f in fails[:40]:
            print(f"  {f['kind']:28} {f['id']:22} {f.get('typed','')} {f.get('spoken','')}  {f['message'][:90]!r}")
    return 0 if ft_pass / max(ft_n, 1) >= 0.98 and seed["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
