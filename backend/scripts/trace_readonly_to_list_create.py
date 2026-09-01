"""Why does a read-only deals question select hubspot.lists.create?

Reproduced live 4/4 on the exact phrasing. `LIST_CREATE_INTENT` does not match it
(no create verb, no "list"/"group"/"segment"), and the pack defaults only fill
args on a plan that already chose the action, so neither is the selector. This
walks the mapper offline to find what actually picks it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MESSAGE = (
    "Show me the most recent deals in our HubSpot pipeline with their amounts and close dates."
)
CLEAN = "Show me the most recent deals in our HubSpot pipeline with amounts."

CONNECTED = ["hubspot", "apollo", "clay", "slack", "gmail"]


def main() -> int:
    from app.services.chat_connector_models import LIST_CREATE_INTENT

    print("=== intent regex ===")
    for label, text in (("reproducing", MESSAGE), ("clean", CLEAN)):
        m = LIST_CREATE_INTENT.search(text)
        print(f"  LIST_CREATE_INTENT [{label}]: {m.group(0) if m else None}")

    from app.services.chat_action_mapper import get_chat_action_mapper

    mapper = get_chat_action_mapper()
    print("\n=== chat action mapper ===")
    for label, text in (("reproducing", MESSAGE), ("clean", CLEAN)):
        plan = None
        for name in ("map_message", "map", "resolve", "plan_for_message", "build_plan"):
            fn = getattr(mapper, name, None)
            if not callable(fn):
                continue
            for kwargs in (
                {"message": text, "connected_integrations": CONNECTED},
                {"message": text},
                {"text": text},
            ):
                try:
                    plan = fn(**kwargs)
                    print(f"  [{label}] via {name}({', '.join(kwargs)})")
                    break
                except TypeError:
                    continue
                except Exception as exc:  # noqa: BLE001
                    print(f"  [{label}] {name} raised {type(exc).__name__}: {exc}")
                    break
            if plan is not None:
                break
        if plan is None:
            print(f"  [{label}] no plan produced by mapper")
        else:
            print(
                f"  [{label}] -> action={getattr(plan, 'invoke_action', None)} "
                f"kind={getattr(plan, 'kind', None)} "
                f"destructive={getattr(plan, 'destructive', None)} "
                f"args={json.dumps(getattr(plan, 'args', None), default=str)}"
            )

    # Score the candidate entries directly — the mapper ranks matrix entries, so
    # the winner and its margin are the useful evidence.
    print("\n=== candidate scoring ===")
    try:
        from app.services.connector_execution_matrix import connector_action_matrix

        entries = [
            e
            for e in connector_action_matrix()
            if str(getattr(e, "connector_id", "")).lower() == "hubspot"
        ]
        print(f"  hubspot entries in matrix: {len(entries)}")
        scorer = getattr(mapper, "_score_entry", None) or getattr(mapper, "score_entry", None)
        if callable(scorer):
            scored = []
            for e in entries:
                try:
                    scored.append((scorer(e, MESSAGE), str(getattr(e, "action_key", ""))))
                except Exception:  # noqa: BLE001
                    try:
                        scored.append((scorer(MESSAGE, e), str(getattr(e, "action_key", ""))))
                    except Exception:  # noqa: BLE001
                        break
            for score, key in sorted(scored, reverse=True)[:12]:
                print(f"    {score:8.2f}  {key}")
        else:
            print("  no per-entry scorer exposed; listing candidate action keys")
            for e in entries[:25]:
                print(f"    {getattr(e, 'action_key', '')}  kind={getattr(e, 'kind', '')}")
    except Exception as exc:  # noqa: BLE001
        print(f"  matrix scoring unavailable: {type(exc).__name__}: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
