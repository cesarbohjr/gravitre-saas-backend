"""Site 4 before/after — does the schema param extractor's model call execute?

Before the fix, `get_model_router(settings)` raised TypeError inside the try, the
`except Exception` logged at warning and returned the heuristic result, so the
extractor was heuristics-only. This runs the real function against a real model
against a message whose argument is only recoverable by reading the sentence,
never by regex, so heuristics-only and model-backed give visibly different
answers.

Mutation control: the pre-fix call shape is re-created deliberately to confirm it
still raises, so the "after" result cannot be mistaken for something that was
working all along.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "delivery" / "site4-schema-param-extractor-probe.json"

ORG = "f07e57c0-1501-4000-8000-c04e57a00001"

# Phrased so the value is buried in prose. A regex looking for `named X` or a
# quoted string finds nothing here.
CASES = [
    (
        "hubspot.lists.create",
        "Could you set something up in HubSpot? We've been calling the segment "
        "Northeast Renewals internally, so use that as the name please.",
    ),
    (
        "hubspot.lists.create",
        "Make me a static list. The team refers to it as Q4 Expansion Targets.",
    ),
]


def load_env() -> None:
    import os

    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


async def main() -> int:
    load_env()
    from app.config import get_settings
    from app.services.model_router import get_model_router
    from app.services.parameter_ledger import ParameterLedger
    from app.services.schema_param_extractor import (
        extract_action_args,
        extract_action_args_heuristic,
    )

    settings = get_settings()

    print("=== the pre-fix call shape, re-created ===")
    try:
        get_model_router(settings)
        before = "NO ERROR — the premise of this whole audit would be wrong"
    except TypeError as exc:
        before = f"TypeError: {exc}"
    except Exception as exc:  # noqa: BLE001
        before = f"{type(exc).__name__}: {exc}"
    print(f"  get_model_router(settings) -> {before}")

    print("\n=== the fixed call shape ===")
    try:
        router = get_model_router()
        after = f"OK — {type(router).__name__}"
    except Exception as exc:  # noqa: BLE001
        after = f"{type(exc).__name__}: {exc}"
    print(f"  get_model_router()         -> {after}")

    results = []
    print("\n=== heuristics-only vs model-backed, real calls ===")
    for action, message in CASES:
        heuristic = extract_action_args_heuristic(
            action, message, ledger=ParameterLedger(), existing_args={}
        )
        try:
            model_backed = await extract_action_args(
                action,
                message,
                ledger=ParameterLedger(),
                existing_args={},
                settings=settings,
                org_id=ORG,
                use_model=True,
            )
            err = None
        except Exception as exc:  # noqa: BLE001
            model_backed, err = {}, f"{type(exc).__name__}: {exc}"

        gained = {
            k: v
            for k, v in (model_backed or {}).items()
            if str(v or "").strip() and not str(heuristic.get(k) or "").strip()
        }
        print(f"\n  message   : {message[:88]}...")
        print(f"  heuristic : {json.dumps(heuristic)}")
        print(f"  with model: {json.dumps(model_backed)}")
        print(f"  gained    : {json.dumps(gained) or '{}'}{'  err=' + err if err else ''}")
        results.append(
            {
                "action": action,
                "message": message,
                "heuristic_only": heuristic,
                "model_backed": model_backed,
                "fields_gained_from_model": gained,
                "error": err,
            }
        )

    any_gain = any(r["fields_gained_from_model"] for r in results)
    payload = {
        "site": "app/services/schema_param_extractor.py:319",
        "pre_fix_call_shape": before,
        "post_fix_call_shape": after,
        "cases": results,
        "verdict": (
            "EXECUTES and adds arguments heuristics could not recover"
            if any_gain
            else "EXECUTES without raising, but added no argument on these cases"
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nVERDICT: {payload['verdict']}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
