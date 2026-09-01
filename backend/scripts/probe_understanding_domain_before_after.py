"""Sites 9 and 10: were these two model calls genuinely dormant, and what changed?

Site 9  contextual_understanding_service.py:225  (_model_extract)
Site 10 domain_intelligence_service.py:208       (_classify_by_llm)

Both were called as get_model_router(self.settings) inside a broad `except
Exception` that logs at WARNING and returns a benign default, so a TypeError from
the zero-arg factory was indistinguishable from "the model had nothing to add".

This runs the REAL code path (not the factory in isolation) against a strict fake
router that (a) rejects any argument exactly as the real zero-arg factory does,
and (b) returns canned JSON when called correctly. So the observable result is
the service's own output: dormant returns the benign default, fixed returns real
extracted values.

Run it once on the fixed tree and once with the two fixes stashed; the driver
`scratch_run_site9_10_before_after.ps1` does both and diffs them. Needs no AI
provider: the fake stands in for the model.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "docs" / "delivery"

# app.config validates required settings at construction, so the environment has
# to be populated before any app import.
import os  # noqa: E402

from probe_classical_region_reach import load_env  # noqa: E402

for _k, _v in load_env().items():
    os.environ.setdefault(_k, _v)

# Long, non-question message: _infer_goal_from_rules yields None only when the
# text does not end in "?" and runs past 12 words, which is the gate on site 9.
MESSAGE = (
    "we need to tighten up the renewal motion for the mid market accounts "
    "before the quarter closes and make sure nothing slips through"
)

SITE9_JSON = '{"goal": "tighten mid-market renewal motion before quarter close", ' \
             '"constraints": ["mid market accounts", "before quarter close"]}'
SITE10_JSON = '{"industry": "software", "department": "customer_success", ' \
              '"subdomain": "renewals", "business_objective": "retention", ' \
              '"execution_type": "analysis", "confidence": 0.82}'


class StrictFakeRouter:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1

        class R:
            content = self.payload

        return R()


def install(payload: str, seen: dict):
    """Replace the factory with one that enforces the real zero-arg signature."""
    import app.services.model_router as mr

    router = StrictFakeRouter(payload)

    def fake_get_model_router(*args, **kwargs):
        if args or kwargs:
            seen["arg_call"] = True
            raise TypeError(
                f"get_model_router() takes 0 positional arguments but {len(args)} was given"
            )
        seen["zero_arg_call"] = True
        return router

    mr.get_model_router = fake_get_model_router  # type: ignore[assignment]
    return router


async def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else "after"
    out = OUT_DIR / f"understanding-domain-{arm}.json"

    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    import app.services.contextual_understanding_service as cus
    import app.services.domain_intelligence_service as dis

    handler = Capture()
    for mod in (cus, dis):
        lg = logging.getLogger(mod.__name__)
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)

    # --- site 9 ---
    seen9: dict = {}
    r9 = install(SITE9_JSON, seen9)
    svc = cus.ContextualUnderstandingService()
    site9_result = await svc._model_extract(MESSAGE, [], [])

    # --- site 10 ---
    seen10: dict = {}
    r10 = install(SITE10_JSON, seen10)
    dom = dis.DomainIntelligenceService()
    # Call the LLM tier directly with a deliberately low-confidence rule result,
    # which is the only condition under which classify() reaches it.
    low_conf = {
        "industry": None,
        "department": None,
        "subdomain": None,
        "business_objective": None,
        "execution_type": None,
        "confidence": 0.1,
        "source": "rules",
        "profile_id": None,
    }
    site10_result = await dom._classify_by_llm(MESSAGE, {}, low_conf)

    warnings = [r.getMessage() for r in records if r.levelno >= logging.WARNING]

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "arm": arm,
        "message": MESSAGE,
        "site9_contextual_understanding": {
            "result": site9_result,
            "goal": site9_result.get("goal"),
            "constraints": site9_result.get("constraints"),
            "router_completions": r9.calls,
            "called_with_arg": bool(seen9.get("arg_call")),
            "called_zero_arg": bool(seen9.get("zero_arg_call")),
        },
        "site10_domain_intelligence": {
            "result": site10_result,
            "department": site10_result.get("department"),
            "confidence": site10_result.get("confidence"),
            "router_completions": r10.calls,
            "called_with_arg": bool(seen10.get("arg_call")),
            "called_zero_arg": bool(seen10.get("zero_arg_call")),
        },
        "warnings": warnings[:8],
    }

    print(f"=== arm: {arm} ===")
    for key in ("site9_contextual_understanding", "site10_domain_intelligence"):
        d = payload[key]
        print(f"\n{key}")
        print(f"  called with arg : {d['called_with_arg']}")
        print(f"  called zero-arg : {d['called_zero_arg']}")
        print(f"  model completed : {d['router_completions']}")
        print(f"  result          : {json.dumps(d['result'])[:200]}")
    for w in warnings[:4]:
        print(f"  WARNING: {w[:150]}")

    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
