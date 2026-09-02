"""Before/after runtime proof that site 8's model call was genuinely dormant.

Runs the REAL `classify_turn_shape` against a router factory that enforces the
real zero-argument signature, once with the buggy line restored and once with
the fix, and reports whether the router was actually entered.

Site 8 needs this more than the earlier sites did, because it failed *closed*:
both arms return shape="task_shaped", so the returned shape proves nothing. The
discriminator is whether `complete()` was ever reached, and whether the reason
string carries the swallowed TypeError.

Run:  python scripts/probe_turn_gate_before_after.py
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "conversational_turn_gate.py"
OUT = ROOT / "docs" / "delivery" / "turn-gate-before-after.json"

FIXED_LINE = "        response = await get_model_router().complete("
BUGGY_LINE = "        response = await get_model_router(settings or get_settings()).complete("

# No data/connector/social/venting/meta signal, so the heuristic declines and the
# model tier is the real decider — the 71.9% bucket measured in probe_turn_gate_reach.
AMBIGUOUS = "Walk me through how we should approach the Q3 board deck."


def load_env() -> None:
    for p in (BACKEND / ".env", ROOT / ".env"):
        if p.exists():
            for k, v in dotenv_values(p).items():
                if v:
                    os.environ.setdefault(k, v)


async def run_arm(arm: str) -> dict[str, Any]:
    """Reload the module under the given source arm and observe router entry."""
    import app.services.model_router as mr

    entered: list[str] = []

    class _Router:
        async def complete(self, **kwargs: Any) -> SimpleNamespace:
            entered.append("MODEL_CALL_START")
            payload = {
                "shape": "mixed",
                "reason": "probe",
                "social_portion": "Walk me through",
                "task_portion": "Q3 board deck",
                "category": "other",
            }
            return SimpleNamespace(parsed=payload, content=json.dumps(payload))

    def _factory(*args: Any, **kwargs: Any):
        # Mirrors the real signature: get_model_router() takes no arguments.
        if args or kwargs:
            raise TypeError(
                "get_model_router() takes 0 positional arguments but "
                f"{len(args)} were given"
            )
        return _Router()

    original_factory = mr.get_model_router
    mr.get_model_router = _factory  # type: ignore[assignment]
    try:
        gate = importlib.reload(importlib.import_module("app.services.conversational_turn_gate"))
        decision = await gate.classify_turn_shape(
            AMBIGUOUS,
            settings=SimpleNamespace(placeholder=True),
            org_id="probe-org",
        )
    finally:
        mr.get_model_router = original_factory  # type: ignore[assignment]

    return {
        "arm": arm,
        "router_entered": bool(entered),
        "shape": decision.shape,
        "used_model": bool(decision.used_model),
        "category": decision.category,
        "reason": (decision.reason or "")[:200],
        "social_portion": decision.social_portion,
        "task_portion": decision.task_portion,
        "swallowed_typeerror": "TypeError" in (decision.reason or ""),
    }


async def main() -> int:
    load_env()
    sys.path.insert(0, str(BACKEND))

    source = SRC.read_text(encoding="utf-8")
    if FIXED_LINE not in source:
        print(f"anchor not found in {SRC} — expected the fixed call site")
        return 1

    results: list[dict[str, Any]] = []
    try:
        SRC.write_text(source.replace(FIXED_LINE, BUGGY_LINE, 1), encoding="utf-8")
        results.append(await run_arm("before (dormant call restored)"))

        SRC.write_text(source, encoding="utf-8")
        results.append(await run_arm("after (fix in place)"))
    finally:
        SRC.write_text(source, encoding="utf-8")
        importlib.reload(importlib.import_module("app.services.conversational_turn_gate"))

    before, after = results
    verdict = (
        "PASS — dormancy confirmed and fixed"
        if (not before["router_entered"] and after["router_entered"])
        else "INCONCLUSIVE — arms did not differ as expected"
    )

    payload = {
        "site": "conversational_turn_gate.py:240 classify_turn_shape",
        "message": AMBIGUOUS,
        "heuristic_declines": True,
        "arms": results,
        "verdict": verdict,
        "note": (
            "Both arms return a usable decision, which is why this site never "
            "looked broken: it failed closed to task_shaped. router_entered and "
            "used_model are the only honest discriminators. Note the before arm "
            "also loses shape=mixed, which is what the social-ack path keys on."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for r in results:
        print(f"\n--- {r['arm']}")
        print(f"  router entered      : {r['router_entered']}")
        print(f"  shape / used_model  : {r['shape']} / {r['used_model']}")
        print(f"  swallowed TypeError : {r['swallowed_typeerror']}")
        print(f"  reason              : {r['reason'][:120]}")
    print(f"\n{verdict}")
    print(f"wrote {OUT}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
