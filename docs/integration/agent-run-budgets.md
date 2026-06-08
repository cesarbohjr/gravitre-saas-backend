# Autonomous run budgets (STA-109)

Hard daily caps on policy-gated auto-execute per operator (agent). Org-wide defaults apply when an operator leaves a limit unset.

## Dimensions

| Dimension | Description |
|-----------|-------------|
| `maxActionsPerDay` | Tool invocations + auto-execute workflow steps |
| `maxTokensPerDay` | LLM tokens attributed to autonomous runs (rollup table) |
| `maxSpendUsdPerDay` | Estimated USD spend for autonomous runs |

Limits reset at UTC midnight. Usage is tracked in `operator_autonomous_usage_daily`.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/enterprise/autonomous-run-budgets` | Org defaults + all agents with limits/usage |
| PUT | `/api/enterprise/autonomous-run-budgets` | Admin: set org-wide defaults |
| GET | `/api/agents/{id}/run-budgets` | Per-agent limits + today's usage |
| PUT | `/api/agents/{id}/run-budgets` | Admin: set per-agent limits; pass `unset: ["maxActionsPerDay"]` to clear |

Org defaults live in `organizations.settings.enterprise.autonomousRunBudgets`:

```json
{
  "maxActionsPerDay": 50,
  "maxTokensPerDay": 100000,
  "maxSpendUsdPerDay": 10
}
```

## Enforcement

- **Auto-execute** — `try_auto_execute_plan_step()` checks before starting a workflow; returns `{ "status": "budget_blocked" }` when blocked.
- **Tool calls** — `invoke_tool()` enforces action budget when workflow parameters include `_autonomous_run` and `operator_id` (set by auto-execute).
- **LLM calls** — `ModelRouter.complete(..., operator_id=..., autonomous_run=True)` records tokens and `cost_usd` into the daily rollup and enforces token/spend caps before the call.

Requires auto-execute mode other than `plan_only` (STA-106).

## Audit

- `operator.auto_execute.budgets_updated` — limits changed
- `operator.auto_execute.budget_blocked` — run blocked by cap

## Related

- STA-106 policy-gated auto-execute — `docs/integration/agent-auto-execute.md`
- STA-92 cost attribution — `GET /api/enterprise/cost-attribution`
