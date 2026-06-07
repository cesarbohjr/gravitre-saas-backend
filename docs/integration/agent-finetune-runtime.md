# Agent fine-tune runtime (STA-99)

Wire org fine-tuned LLM models into workflow agent inference with base-model fallback and audit logging.

## Data model

- `agents.trained_model_id` → `trained_models` (optional assignment)
- `training_jobs.trained_model_id` set when a job completes
- `model_calls` extended with `agent_id`, `trained_model_id`, `trained_model_version`, `used_fallback`

Fine-tuned OpenAI model ids are stored on `model_versions.metrics.custom_metrics.fine_tuned_model` after training worker deploy.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/training/workflow-agents` | List workflow agents (`agents` table) |
| GET | `/api/training/fine-tuned-models` | List deployable `fine_tuned_llm` models |
| GET | `/api/training/agents/{id}/fine-tuned-model` | Current assignment |
| PUT | `/api/training/agents/{id}/fine-tuned-model` | Assign or clear (admin) |

## Runtime

`handoff_service.run_agent_task` calls `complete_for_agent`, which:

1. Resolves deployed fine-tuned OpenAI id from assigned `trained_models` row
2. Calls `ModelRouter.complete` with `model_override` when available
3. On `AllProvidersFailedError`, `ProviderInvalidResponseError`, or `ValueError`, retries with agent base model
4. Writes audit event `agent.model.inference` and logs `model_calls` with version metadata

Guardrail failures from the router do not trigger fallback.

## UI

Training Hub → **Agent Fine-Tuned Models** section assigns models to workflow agents.
