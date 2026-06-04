# Council → workflow branch (STA-48)

When agent confidence is low, escalate to an **agent council**; downstream steps run only on the selected branch.

## Flow

```text
Sales agent step (confidence in output)
  → council step (escalates if confidence < threshold)
    → branch: enroll | nurture
  → agent steps with config.when_branch = enroll | nurture (others skipped)
```

## Council step

Step type: `council` (executable in dry-run and execute).

| Config key | Description |
|------------|-------------|
| `source_step_id` | Prior step whose `confidence` triggers escalation |
| `confidence_threshold` | Escalate when below (default `0.75`; agent uses 0–100) |
| `objective` | Council question |
| `options` | Vote options (e.g. `["enroll", "nurture"]`) |
| `output_paths` | Map council recommendation → branch id |
| `agent_ids` | Org agents to seat on council (loads from DB) |
| `decision_method` | `majority_vote`, `weighted_vote`, `unanimous`, `chair_decides` |

Output includes `branch`, `escalated`, `final_recommendation`, `final_confidence`, `council_session_id`.

## Branch routing

Any step may set `config.when_branch`. During execute, steps are **skipped** when the active branch (from the latest council output) does not match.

## Demo workflow

**Uncertain lead → Council → Enroll or nurture** is upserted on org seed and HubSpot connect.

Stable id: `organizations.settings.onboarding.demo_council_workflow_id`

## Builder

`council` canvas nodes compile to `council` steps (not `noop`). Pass `councilConfig` / `outputPaths` in node metadata.

## Code

- `backend/app/services/council_workflow_service.py`
- `backend/app/services/council_service.py`
- `backend/app/workflows/handlers.py` — `CouncilStepHandler`
- `backend/app/workflows/execute.py` — branch skip logic

## Related

- [AGENT_HANDOFFS.md](./AGENT_HANDOFFS.md)
- [WORKFLOW_BUILDER.md](./WORKFLOW_BUILDER.md)
