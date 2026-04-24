# Phase 7: Step Handler Registry

## Current Architectural Limitation
- Step logic is hard‑coded in `execute.py` and `dry_run.py`.
- Adding or evolving step types requires edits in multiple modules.

## Target Architecture
- Central registry of step handlers keyed by `step_type`.
- Each handler implements `validate`, `simulate`, `execute`, and `audit`.
- Execute and dry‑run both dispatch through the registry.

## Minimal Implementation Plan
- Add `backend/app/workflows/registry.py` with `StepHandler`, `StepContext`, and registry functions.
- Add `backend/app/workflows/handlers.py` with default handlers for existing steps.
- Update `execute.py` and `dry_run.py` to call `get_handler(...).execute/simulate`.

## Required Migrations
- None.

## Integration Changes
- `execute_workflow_steps` now dispatches via registry.
- `execute_dry_run` now dispatches via registry.
- Existing approval gating, rate limiting, and kill switches remain enforced inside handlers.

## Risks
- Handler registration order issues if registry is not imported.
- Divergence between simulate and execute behavior if handlers are inconsistent.

## Future Scaling Notes
- Register new step types without editing core engines.
- Add handler discovery hooks if a plugin mechanism is introduced later.
