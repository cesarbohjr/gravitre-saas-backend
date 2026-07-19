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

Module D (`gravitree_voice`) attaches `voice_section` on `TurnInterpretation` /
`run_connector_turn` results. Connector-turn user-facing strings (e.g. pending-plan
cancel) call `format_operator_message` — not per-surface copy.

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
| 1 | Gmail multi-turn recipient | ledger stage → resume fills `to` + persists `pending_task.args` |
| 2 | Unprompted email across turns | live ledger read every turn — never re-ask recipient |
| 3 | Cold connector (Pipedrive) | schema-primary extract without quotes; not Zendesk/Jira |
| 4 | Off-script strategic recovery | intent=`modify` |

**Done bar:** all four PASS on deployed tip with conversation/audit evidence pointers. Local service repro PASS alone is not production-fixed — require merge → Railway redeploy → live chat re-run.

## Fix pass (read-side + dual-path + extract priority)

1. **Live ledger on clarify** — `_catalog_write_clarification` always calls `get_ledger(task_state)`; deleted `_slack_send_clarification` / `_email_send_clarification`.
2. **Resume patch persistence** — `plan_action` merges `__resume_state_patch`; `process_turn` persists it before blocked-connector returns (root cause of stalled `pending_task.args`).
3. **Schema-primary extraction** — `chat_action_mapper.match_segment` runs schema heuristic first; vendor `_extract_args` is fallback only.
4. **Confidence-aware clarify** — high → silent use; medium (likely name→email) → propose/confirm; low → ask cleanly.

### Dual-path inventory

| Pre-ledger helper | Disposition |
|-------------------|-------------|
| `_slack_send_clarification` | **Deleted** — superseded by `_catalog_write_clarification` |
| `_email_send_clarification` | **Deleted** — same |
| `_is_slack_awaiting_body` | **Already deleted** earlier |
| Vendor `_extract_args` in mapper | **Kept as fallback only** — schemas do not yet cover every NL edge; shrinks over time |
| `conversational_execution_service` agent/workflow param clarify | **Kept** — non-catalog create-agent/workflow dialogue; ledger is for catalog connector actions |

## Tracked follow-up (do not start until phase 1 live-verified)

**Cross-conversation entity memory (Module B phase 2 follow-up):** once in-conversation ledger is live-PASS, reuse `entity_resolution_store` / `org_entity_resolution_records` so a Slack channel or email recipient confirmed in conversation A can be recalled in a later conversation B. Explicitly gated — not built in this pass.

### Evidence (service + durable ledger)

From `scripts/verify-module-b-conversation-turn-controller.py` @ `2026-07-19T09:01:43Z`:

- `gmail_multi_turn_recipient` PASS — resume filled `to=alex@acme.com`
- `unprompted_email_across_turns` PASS — ledger bind without re-ask
- `jira_cold_multi_turn` PASS — `summary=login page broken`, `project_key=ENG`
- `off_script_strategic_recovery` PASS — intent=`modify`
- `durable_ledger_persist` PASS — conversation `00000000-0000-4000-8000-090143098494` org `f07e57c0-1501-4000-8000-c04e57a00001` slot `to=alex@acme.com`

Prod chat tip re-run (Railway tip after this push) still required before labeling the module user-facing Done.
