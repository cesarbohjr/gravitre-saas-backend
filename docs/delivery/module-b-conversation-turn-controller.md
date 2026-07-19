# Module B — Conversation Turn Controller

## Standing rule

No per-connector staging. Slack’s old `awaiting_params` path is replaced by a shared conversation-scoped parameter ledger. Every catalog action with a workflow schema inherits multi-turn resume automatically.

## Architecture

| Piece | Module |
|-------|--------|
| Parameter ledger | [`backend/app/services/parameter_ledger.py`](../../backend/app/services/parameter_ledger.py) |
| Schema-constrained extraction (FAST) | [`backend/app/services/schema_param_extractor.py`](../../backend/app/services/schema_param_extractor.py) |
| Turn controller (chat / ReAct / canvas) | [`backend/app/services/conversation_turn_controller.py`](../../backend/app/services/conversation_turn_controller.py) |
| Durable store | `conversations.task_state.parameter_ledger` via [`conversation_state_service.py`](../../backend/app/services/conversation_state_service.py) |

```
Surfaces (chat · ReAct · canvas)
        │
        ▼
conversation_turn_controller
        │
        ├── parameter_ledger (ingest / bind / stage / resume)
        ├── schema_param_extractor (TaskType.CLASSIFICATION)
        └── pending-plan intent (continue | modify | cancel)
                │
                ▼
        catalog write authority → risk → execute
```

Meson UI is unchanged. Meson reasoning unification is a deferred sub-phase.

## Phases shipped

### Phase 1 — Parameter ledger

- Write-on-mention ingest (email, channel, project key, quotes)
- Generic `stage_awaiting_params` / `resume_awaiting_params`
- Slack-only staging removed from clarification + `plan_action`
- Legacy `clarified_params.slack_channel` bridged into ledger on load

### Phase 2 — Schema-constrained extraction

- Heuristic + FAST-tier model extraction constrained to `get_workflow_schema` fields
- Wired into `process_turn` and `chat_action_mapper` write path

### Phase 3 — One planner entry

- `run_connector_turn` used by governed chat and ReAct fallback
- Canvas `invoke_tool` binds args via `enrich_canvas_step_config_from_ledger`

### Phase 4 — Dead-end recovery

- `classify_pending_plan_intent` replaces CONFIRM_PATTERN-only trapping for orphan strategic plans
- Off-script modify language clears advisory `current_plan` and continues with the user’s instruction

## Verification

Run:

```bash
python scripts/verify-module-b-conversation-turn-controller.py
```

Artifact: [`module-b-conversation-turn-controller-live.json`](module-b-conversation-turn-controller-live.json)

### Four audit repros

| # | Repro | Gate |
|---|-------|------|
| 1 | Gmail multi-turn recipient | ledger stage → resume fills `to` |
| 2 | Unprompted email across turns | ingest turn1 → bind on “send email” later |
| 3 | Jira cold multi-turn | schema extract without quotes |
| 4 | Off-script strategic recovery | intent=`modify` |

**Done bar:** all four PASS on deployed tip with conversation/audit evidence pointers. Local service repro PASS alone is not production-fixed — require merge → Railway redeploy → live chat re-run.

### Evidence (service + durable ledger)

From `scripts/verify-module-b-conversation-turn-controller.py` @ `2026-07-19T09:01:43Z`:

- `gmail_multi_turn_recipient` PASS — resume filled `to=alex@acme.com`
- `unprompted_email_across_turns` PASS — ledger bind without re-ask
- `jira_cold_multi_turn` PASS — `summary=login page broken`, `project_key=ENG`
- `off_script_strategic_recovery` PASS — intent=`modify`
- `durable_ledger_persist` PASS — conversation `00000000-0000-4000-8000-090143098494` org `f07e57c0-1501-4000-8000-c04e57a00001` slot `to=alex@acme.com`

Prod chat tip re-run (Railway tip after this push) still required before labeling the module user-facing Done.
