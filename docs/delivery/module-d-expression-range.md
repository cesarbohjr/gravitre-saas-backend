# Module D — Expression range (phrase variety)

Expands **how many ways** Gravitree can say the same category of thing.
Does **not** change classification, turn-controller intent, or Module B range-expansion logic.

SoT: [`voice_expression_range.py`](../../backend/app/services/voice_expression_range.py) +
[`gravitree_voice.py`](../../backend/app/services/gravitree_voice.py).

## Part 1 — Recurring response categories

| Category | Call sites (approx) | Was identical? | This pass |
|----------|--------------------:|----------------|-----------|
| `connector_connect_to_run` | 5 | yes | **varied** |
| `tool_error.connector_not_connected` | dynamic adapter | yes | **varied** |
| `tool_error.auth_expired` / `missing_scope` / `tool_not_available` | envelope + adapter | yes | **varied** |
| `tool_error.validation_error` / `rate_limited` / `connector_timeout` / `permission_denied` / … | adapter | yes | **varied** |
| `missing_parameters_header` ("Still needed:") | `format_operator_response` | yes | **varied** |
| `success_win` / `success_win_light` | Meson + digest | mostly | **varied** |
| `blocked_generic` | Meson / envelope / alerts | template-identical | **varied** |
| `insufficient_info` / `assumption_flag` / `estimate_prefix` | voice helpers | yes | **varied** |
| `correction_ack` | agent_intelligence | yes | **varied** |
| `pending_plan_cancelled` | turn controller + connector | yes | **varied** |
| `skipped_unsupported` / `no_executable_action` / `skipped_connector` | orch / matrix | yes | **varied** |
| `write_approval` / `write_approval_required` | workflows / envelope | shaped by details | **excluded** |
| `canvas_write_blocked` | canvas gate | yes | **excluded** |
| `approval_needed_requester(+title)` | connector + workflows | yes | **excluded** |
| `notification_run_title` / `audit_failure_summary` / `failure_alert_title` | outcomes / alerts | status-branched | **excluded** |

### Excluded (precision / auditability)

- Write approval prompts and `write_approval_required` — exact CTA + governance wording
- Canvas write-blocked — approval-count / authority copy must stay exact
- Approval-queue requester title/body — Decision Queue signals
- Notification run titles, audit failure summaries, failure alert titles — status labels for ops/audit

## Part 3 — Selection

- State key: `conversations.task_state.voice_expression_last` → `{category: last_index}`
- Bound per connector turn in `run_connector_turn` via contextvar
- Rule: `next = 0` if unset; else `(last + 1) % n` — deterministic, no RNG
- Without bound state (unit tests, one-off), always index `0` (canonical HOUSE line)

## Verification

```bash
pytest backend/tests/services/test_voice_expression_range.py \
  backend/tests/services/test_gravitree_voice.py -q
python scripts/verify-module-d-expression-range-live.py
```

Artifact: [`module-d-expression-range-live.json`](module-d-expression-range-live.json)

## Live evidence (2026-07-21)

- Tip: `44d13f3b2dd23c0d40e92168c081615e0fc6f813` on `https://api.gravitre.app/health`
- Battery: **PASS** — `connectishDistinct=3` in one conversation; excluded kinds stable; fact-consistency 6/6 for `connector_connect_to_run`
- Root-cause fix for rotation: `voice_expression_last` must live in `DEFAULT_TASK_STATE` or `_normalize_state` strips it
