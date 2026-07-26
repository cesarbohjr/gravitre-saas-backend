# Module B — Permanent Architecture Reference

This document records intentional leftovers and product decisions so future
engineers do not rediscover and re-litigate them as bugs.

## Standing rule

No per-connector staging or clarify paths for catalog writes. Shared surfaces:

| Concern | Module |
|---------|--------|
| Conversation-scoped parameter ledger | `backend/app/services/parameter_ledger.py` |
| Schema-constrained extraction | `backend/app/services/schema_param_extractor.py` |
| Shared turn controller | `backend/app/services/conversation_turn_controller.py` |
| Generic catalog write clarify | `ClarificationEngine._catalog_write_clarification` |

## Deleted dual paths (do not restore)

| Helper | Why deleted |
|--------|-------------|
| `_slack_send_clarification` | Superseded by `_catalog_write_clarification` + ledger |
| `_email_send_clarification` | Same |
| `_is_slack_awaiting_body` | Ledger `pending_missing` covers resume |

## Intentional leftovers (keep)

### 1. Vendor `_extract_args` in `chat_action_mapper`

**Status:** Fallback only after schema-primary heuristic / FAST extract.

**Why kept:** Workflow schemas do not yet cover every NL edge case. Schema
extraction runs first; vendor regex fills gaps. Shrink over time as schemas
improve — do not delete until a catalog-wide sweep shows zero meaningful
fallback reliance.

### 2. `conversational_execution_service` agent / workflow clarify

**Status:** Kept.

**Why kept:** Create-agent / create-workflow dialogue is **not** a catalog
connector action. The parameter ledger is for connector catalog writes
(`gmail.messages.send`, `slack.post_message`, etc.). Mixing those dialogues
into the ledger would conflate product surfaces.

### 3. `priority_connector_tools._gmail_*` executors

**Status:** Kept.

**Why kept:** These are **API execution adapters** (drafts, labels, threads,
batch, watch) — not NL staging/clarify helpers. They map invoke actions to
Gmail HTTP calls. Deleting them would break governed execution, not dual-path
staging.

### 4. Slack NL helpers (`_slack_channel_label`, `_slack_message_body`)

**Status:** Kept as generic-path NL helpers when present.

**Why kept:** They normalize user phrasing into args for the shared catalog
path; they do not stage `awaiting_params` themselves.

## Product decision — connector-unavailable vs advisory plan-first

| User intent | Correct behavior |
|-------------|------------------|
| **Execute-now** connector write (send Slack, create Apollo list *now*) | Short-circuit immediately when the connector is not Connected. Do **not** stage an advisory `current_plan`. |
| **Plan-first / advisory** (`show the plan first`, `do not execute yet`, `plan only`) | Do **not** short-circuit on missing connectors. Stage `current_plan` and list missing connectors as blockers in the plan. |

**Implication for audit test 4:** The original Round-2 failure (Slack
“not Connected” before any plan) was testing execute-now short-circuit on a
message that also asked for a plan. After the advisory fix, that message must
stage `current_plan`. Short-circuiting without a plan is correct only for
execute-now intents.

## Confidence-propose (medium tier)

High → silent use · Medium → propose/confirm · Low → clean ask.

**Corruption class (Round-2):** Never embed `EMAIL_RE` after a greedy
`[^@]+` gap. Extract complete emails first (`extract_complete_emails`), then
score name→local-part tokens. Proposed values must appear **verbatim** in
conversation context. Regression:
`backend/tests/services/test_confidence_propose_email_corruption.py`.

If this class regresses without a clean fix, **disable** medium propose
(fall back to clean-ask) rather than ship confidently-wrong proposals.

## Phase 2 — Cross-conversation entity memory

Reuse `entity_resolution_store` / `org_entity_resolution_records`
(`cross_conversation_ledger_memory.py`).

**Feature flag:** `Settings.cross_conversation_ledger_memory_enabled`
(**default True**). Set `CROSS_CONVERSATION_LEDGER_MEMORY_ENABLED=false` to disable.
