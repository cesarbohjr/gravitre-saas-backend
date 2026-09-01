"""Close out schema_param_extractor's INCONCLUSIVE status.

The get_model_router() arity fix is deployed, but the functional claim — that the
model call now extracts arguments the heuristics genuinely cannot — was never
proven. The earlier probe returned before the model call because the action it
used had no registered workflow schema, so `_schema_field_keys` was empty.

To reach the model call, all of these must hold:
  1. `get_workflow_schema(action)` returns a schema with `required_fields`
  2. at least one required field is NOT filled by the heuristic pass
  3. use_model=True

So this first enumerates the real catalog to find actions that genuinely satisfy
(1), then constructs a message that satisfies (2), then calls the real extractor
and reports whether the model contributed an argument the heuristic did not.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "delivery" / "schema-param-extractor-proof.json"


def load_env() -> None:
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue


async def main() -> int:
    load_env()
    from app.connectors.action_catalog.action_workflow_schema import (
        get_workflow_schema,
        iter_workflow_fields,
    )
    from app.services.schema_param_extractor import (
        _schema_field_keys,
        extract_action_args,
        extract_action_args_heuristic,
    )

    # 1. Which actions actually have a schema the extractor can work from?
    try:
        from app.connectors.action_catalog.action_workflow_schema import (
            WORKFLOW_SCHEMAS,  # type: ignore[attr-defined]
        )

        candidates = list(WORKFLOW_SCHEMAS)
    except Exception:  # noqa: BLE001
        from app.connectors.action_catalog.action_parameters import ACTION_PARAMETERS

        candidates = list(ACTION_PARAMETERS)

    with_schema: list[dict] = []
    for action in candidates:
        schema = get_workflow_schema(action)
        if not schema:
            continue
        req = [f for f in schema.required_fields if f.arg_keys]
        if not req:
            continue
        with_schema.append(
            {
                "action": action,
                "required": [(f.label, f.arg_keys[0]) for f in req],
                "all_fields": [
                    (f.label, f.arg_keys[0]) for f in iter_workflow_fields(schema) if f.arg_keys
                ],
            }
        )

    print(f"catalog actions inspected: {len(candidates)}")
    print(f"actions with a workflow schema AND required fields: {len(with_schema)}")
    for row in with_schema[:15]:
        print(f"  {row['action']}: required={row['required']}")

    if not with_schema:
        print("\nNO action has a schema with required fields — the model call is unreachable.")
        OUT.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "verdict": "UNREACHABLE",
                    "reason": "no catalog action exposes a workflow schema with required fields",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1

    # 2. Find a case where the heuristic leaves a required field empty.
    reachable: list[dict] = []
    message = (
        "Please go ahead and set that up for the account we discussed on the call "
        "earlier this week, the usual arrangement, thanks."
    )
    for row in with_schema:
        action = row["action"]
        keys = _schema_field_keys(action)
        if not keys:
            continue
        heur = extract_action_args_heuristic(action, message)
        schema = get_workflow_schema(action)
        missing = [
            f.label
            for f in schema.required_fields
            if f.arg_keys and not str(heur.get(f.arg_keys[0]) or "").strip()
        ]
        if missing:
            reachable.append({**row, "heuristic": heur, "missing": missing})

    print(f"\nactions where the heuristic leaves a required field empty: {len(reachable)}")
    if not reachable:
        print("heuristics fill every required field — model call never needed")
        return 1
    for row in reachable[:8]:
        print(f"  {row['action']}: missing={row['missing']} heuristic={row['heuristic']}")

    # 3. Run the real extractor, model enabled, on the first few reachable cases.
    print("\n=== live extractor runs (model enabled) ===")
    results = []
    for row in reachable[:5]:
        action = row["action"]
        heur = row["heuristic"]
        try:
            got = await extract_action_args(action, message, use_model=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {action}: RAISED {type(exc).__name__}: {exc}")
            results.append({"action": action, "error": f"{type(exc).__name__}: {exc}"})
            continue
        added = {k: v for k, v in got.items() if str(heur.get(k) or "") != str(v or "")}
        print(f"  {action}")
        print(f"    heuristic  = {json.dumps(heur)}")
        print(f"    extractor  = {json.dumps(got)}")
        print(f"    model added= {json.dumps(added)}  ({len(added)} key(s))")
        results.append(
            {
                "action": action,
                "missing_after_heuristic": row["missing"],
                "heuristic_args": heur,
                "extractor_args": got,
                "model_contributed": added,
            }
        )

    contributed = [r for r in results if r.get("model_contributed")]
    errored = [r for r in results if r.get("error")]
    no_typeerror = not any("TypeError" in str(r.get("error") or "") for r in results)

    print("\n=== VERDICT ===")
    print(f"model call reached on {len(results)} action(s)")
    print(f"no TypeError from get_model_router: {no_typeerror}")
    if contributed:
        print(f"PASS — model contributed arguments on {len(contributed)} action(s)")
        verdict = "PASS"
    elif errored:
        print(f"FAIL — {len(errored)} action(s) errored: {[r['error'] for r in errored]}")
        verdict = "FAIL"
    else:
        print("PARTIAL — model call executed and returned no extra args.")
        print("  The arity fix is proven (no TypeError), but this message shape gave")
        print("  the model nothing confident to add, which is correct behaviour, not")
        print("  proof of added capability.")
        verdict = "PARTIAL"

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "verdict": verdict,
                "message_used": message,
                "actions_with_required_schema": len(with_schema),
                "actions_reaching_model_call": len(reachable),
                "runs": results,
                "no_type_error": no_typeerror,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
