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

## Architecture leftovers (permanent)

See [`module-b-architecture-reference.md`](module-b-architecture-reference.md) for the
intentional leftover set (vendor `_extract_args` fallback, conversational
agent/workflow clarify, `_gmail_*` executors) and the connector-unavailable vs
advisory plan-first product decision.

## Confidence-propose corruption fix (Round-2)

**Root cause:** greedy name→email regex
`\b{name}\b[^@\n]{0,40}(EMAIL_RE)` backtracked into dotted local-part suffixes
(`moduleb@acme.test` inside `sarah.chen.moduleb@acme.test`). Not truncation of a
correct ledger value; wrong capture entirely.

**Fix:** `extract_complete_emails()` + promote path that scores complete emails
only; proposed value must appear verbatim in corpus. Regression:
`backend/tests/services/test_confidence_propose_email_corruption.py`.

## Advisory plan-first (test 4 root cause)

Two bugs stacked: (1) Slack connector_unavailable short-circuit ignored
“show the plan first”; (2) `should_plan` returned False because
“strategic multi-step plan” did not match phrase `"make a plan"`. Fixed via
`is_advisory_plan_first` → skip short-circuit/preflight + force `should_plan`.

## Phase 2 — Cross-conversation entity memory (built, OFF by default)

Reuse `entity_resolution_store` via
`backend/app/services/cross_conversation_ledger_memory.py`.

**Flag:** `Settings.cross_conversation_ledger_memory_enabled = False` until
phase-1 live 4/4 + confidence-propose fix are confirmed on a deployed tip.

### Evidence (live prod cert — required Done bar)

From `scripts/audit-module-b-live-cert.py` @ tip `d9ed9f4e` — artifact [`module-b-live-cert-audit.json`](module-b-live-cert-audit.json):

| Test | Verdict | Evidence |
|------|---------|----------|
| 1 Gmail multi-turn | **PASS** | conversation `3f60b6ae-6218-48e9-aaa6-5c122d4d4c60` — turn2 bound recipient in ledger/`pending_task.args` |
| 2 Unprompted email | **PASS** | conversation `4681c262-4c64-4784-8298-dea271af6f69` — turn1 ledger wrote `renewals.moduleb@acme.test`; turn4 did not re-ask recipient |
| 3 Cold Pipedrive | **PASS** | conversation `a7e64ac3-ce62-49c3-a00d-a309295a80f8` — title bound without quotes |
| 4 Off-script recovery | **PASS** | conversation `0e414f65-a094-4828-9405-a3581620ecc3` — modify path adapted |

`universal_memory_verdict`: **UNIVERSAL** (dual-path deleted, schema-primary extract, resume patch persisted).

### Round-2 re-verify (corruption + advisory fix) — tip `c0655c10`

From `scripts/audit-module-b-round2-reverify.py` — artifact [`module-b-round2-reverify.json`](module-b-round2-reverify.json).
Includes `e4c5ea09` (corruption + should_plan) and `c0655c10` (advisory skip catalog clarify).

| Test | Verdict | Evidence |
|------|---------|----------|
| 1 Gmail multi-turn | **PASS** | conversation `9e35cbd6-ce92-48a8-b2f0-7801dc9ebf80` |
| 2 Unprompted email | **PASS** | conversation `68b0c975-938a-42cb-becd-a03e5eef6e43` |
| 3 Cold Intercom | **PASS** | conversation `a3b52219-0d97-4d14-a7d7-8a8492b56f62` |
| 4 Off-script recovery | **PASS** | conversation `34cd48f0-91f4-441a-be65-c3189a427764` — “Plan only”; revise → Slack-first / skip enrichment |
| 8 Confidence propose | **PASS** | conversation `fb3876b5-d8a5-4407-98f8-10869055cfd6` — full `sarah.chen.moduleb@acme.test`; no suffix corruption |

Schema sweep: [`module-b-schema-extraction-sweep.json`](module-b-schema-extraction-sweep.json) — 79 coverable write actions PASS, 0 FAIL_EMPTY.
Architecture reference: [`module-b-architecture-reference.md`](module-b-architecture-reference.md).
