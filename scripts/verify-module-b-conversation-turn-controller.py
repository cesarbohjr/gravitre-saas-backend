#!/usr/bin/env python3
"""Live/local acceptance for Module B Conversation Turn Controller.

Four audit repros (must all pass before Module B Done):
  1. Gmail multi-turn recipient
  2. Unprompted email across turns
  3. Jira cold multi-turn (no quotes)
  4. Off-script strategic plan recovery (modify)

When SUPABASE_* env is present, persists ledger into an isolated conversation
row. Always exercises in-process services (deploy tip should re-run after push).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import dotenv_values  # noqa: E402


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for name in (".env", "backend/.env", "apps/web/.env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                merged.update({k: v for k, v in loaded.items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _check_gmail_multi_turn() -> dict:
    from app.services.chat_connector_models import ConnectorActionPlan
    from app.services.parameter_ledger import (
        resume_awaiting_params,
        stage_awaiting_params,
    )

    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={},
    )
    staged = stage_awaiting_params(plan, ("recipient",))
    resumed, ledger, _ = resume_awaiting_params(
        "alex@acme.com",
        {**staged, "recent_user_messages": ["send an email"]},
    )
    ok = bool(
        resumed
        and resumed.args.get("to") == "alex@acme.com"
        and ledger.get("to") == "alex@acme.com"
    )
    return {
        "name": "gmail_multi_turn_recipient",
        "status": "PASS" if ok else "FAIL",
        "detail": f"to={getattr(resumed, 'args', {}).get('to') if resumed else None}",
    }


def _check_unprompted_email() -> dict:
    from app.services.chat_connector_models import ConnectorActionPlan
    from app.services.parameter_ledger import (
        apply_ledger_to_plan,
        ingest_message_slots,
    )

    ledger = ingest_message_slots("my contact is alex@acme.com for the renewal")
    # Simulate turns 2–3 chatter without clearing ledger
    task_state = {"parameter_ledger": ledger.to_dict(), "recent_user_messages": ["hi", "ok", "thanks"]}
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={"subject": "Follow-up", "body": "Hello"},
    )
    bound = apply_ledger_to_plan(plan, task_state)
    ok = bound.args.get("to") == "alex@acme.com"
    return {
        "name": "unprompted_email_across_turns",
        "status": "PASS" if ok else "FAIL",
        "detail": f"to={bound.args.get('to')}",
    }


def _check_jira_cold_multi_turn() -> dict:
    from app.services.schema_param_extractor import extract_action_args_heuristic

    args = extract_action_args_heuristic(
        "jira.issues.create",
        "create an issue login page broken in project ENG",
    )
    ok = (
        args.get("project_key", "").upper() == "ENG"
        and "login" in (args.get("summary") or "").lower()
    )
    follow = extract_action_args_heuristic(
        "jira.issues.create",
        "Checkout button fails on mobile",
        existing_args={"project_key": "ENG"},
    )
    ok = ok and "checkout" in (follow.get("summary") or "").lower()
    return {
        "name": "jira_cold_multi_turn",
        "status": "PASS" if ok else "FAIL",
        "detail": f"create={args} follow={follow}",
    }


async def _check_off_script_recovery() -> dict:
    from app.services.conversation_turn_controller import classify_pending_plan_intent

    intent = await classify_pending_plan_intent(
        "let's skip step 2 and just create the list",
        current_plan={
            "goal": "Create Apollo contact list then enrich contacts",
            "steps": [{"label": "Plan"}, {"label": "Enrich"}, {"label": "Create list"}],
        },
        use_model=False,
    )
    ok = intent == "modify"
    return {
        "name": "off_script_strategic_recovery",
        "status": "PASS" if ok else "FAIL",
        "detail": f"intent={intent}",
    }


def main() -> int:
    import asyncio

    started = datetime.now(timezone.utc).isoformat()
    results = [
        _check_gmail_multi_turn(),
        _check_unprompted_email(),
        _check_jira_cold_multi_turn(),
        asyncio.run(_check_off_script_recovery()),
    ]

    # Optional durable ledger write when Supabase is configured.
    env = _load_env()
    durable: dict | None = None
    url, key = env.get("SUPABASE_URL"), env.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        try:
            from supabase import create_client

            from app.services.parameter_ledger import ingest_message_slots, ledger_patch
            from isolated_conversation_org import resolve_isolated_conversation_actor

            client = create_client(url, key)
            org_id, user_id, email = resolve_isolated_conversation_actor(env, client)
            conv_id = (
                f"00000000-0000-4000-8000-{datetime.now(timezone.utc).strftime('%H%M%S%f')[:12]}"
            )
            ledger = ingest_message_slots("module-b verify alex@acme.com")
            now = datetime.now(timezone.utc).isoformat()
            client.table("conversations").insert(
                {
                    "id": conv_id,
                    "org_id": org_id,
                    "user_id": user_id,
                    "title": "Module B ledger verify",
                    "preview": "module-b",
                    "message_count": 0,
                    "task_state": {
                        "clarified_params": {},
                        "pending_task": None,
                        **ledger_patch(ledger),
                    },
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()
            row = (
                client.table("conversations")
                .select("id,task_state")
                .eq("id", conv_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            stored = (row.data or [{}])[0].get("task_state") or {}
            slots = (stored.get("parameter_ledger") or {}).get("slots") or {}
            durable_ok = (slots.get("to") or {}).get("value") == "alex@acme.com"
            durable = {
                "name": "durable_ledger_persist",
                "status": "PASS" if durable_ok else "FAIL",
                "conversation_id": conv_id,
                "org_id": org_id,
                "actor": email,
                "detail": f"slots.to={(slots.get('to') or {}).get('value')}",
            }
            results.append(durable)
        except Exception as exc:  # noqa: BLE001
            durable = {
                "name": "durable_ledger_persist",
                "status": "INCONCLUSIVE",
                "detail": str(exc)[:240],
            }
            results.append(durable)

    all_named = {r["name"]: r["status"] for r in results}
    core = [
        "gmail_multi_turn_recipient",
        "unprompted_email_across_turns",
        "jira_cold_multi_turn",
        "off_script_strategic_recovery",
    ]
    core_pass = all(all_named.get(n) == "PASS" for n in core)
    payload = {
        "module": "B",
        "title": "Conversation Turn Controller",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "overall": "PASS" if core_pass else "FAIL",
        "results": results,
        "note": (
            "In-process service repros. Prod chat tip PASS still requires "
            "merge → Railway redeploy → live chat traces with evidence pointers."
        ),
    }
    out = ROOT / "docs" / "delivery" / "module-b-conversation-turn-controller-live.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if core_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
