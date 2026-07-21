# BusinessOutcome Phases 1–4 — delivery

**Built on tip base:** `0a389d27`  
**Phase 0 audit:** `docs/delivery/business-outcome-phase0-wiring-audit.md`

## Prior confirmations (closed before this program)

1. Read surface → action follow-up: PASS tip `5997045b`, conv `77178525-d5ad-4671-936c-dc1610c4d0e8`
2. Completion-rec never reaches `invoke_tool` / `execute_write_action`: PASS `test_post_action_experience.py` AST + `assert_no_execute_surface`

## Phase 1 — Projection

- `backend/app/services/business_outcome/` — models, projector, ordered pipeline
- `GET /api/business-outcomes`, `GET /{id}`, `GET /{id}/export` — one DTO, no consumer branching
- Chat enrich attaches the same DTO via `run_business_outcome_pipeline`

## Phase 2 — Diff / Undo

- `ActionSpec.compensating_action` / `supports_diff` catalog properties
- `catalog_reversal` is the query surface; compensation seeds ActionSpec during migration
- `authorize_compensation_write` + `POST /api/business-outcomes/{id}/undo` gate through `catalog_write_authority`
- Irreversible actions (e.g. `gmail.messages.send`) get honest Undo section — never a fake reverse

## Phase 3 — Chat renderer

- `BusinessOutcomeView` — zero business logic; renders DTO sections only when present
- Wired in `chat-execution-panel.tsx` when `business_outcome` / `structured.businessOutcome` present

## Phase 4 — Shared surfaces

- Same `BusinessOutcomeView` on `/runs/[id]` (`density=timeline`)
- Export = serialize same DTO (JSON/markdown)
- Code-level shared import proven in `test_business_outcome.py::test_shared_frontend_renderer_single_component`

## Lifecycle — shipped vs intentional omissions

| Shipped (real triggers) | Intentional omissions (not backlog) |
|-------------------------|-------------------------------------|
| created, verified, presented, approved, undone | reviewed, edited, referenced, archived |

**Intentional section omissions (same rule):** Impact, Related Outcomes, Dependencies, History — never fabricated; enable only when Module A / edges have real backing. See Phase 0 audit § “intentional omissions vs unfinished work.”

Phases 1–4 **code** is on `main`. Phase 4 is **not closed** until live tip advances and `verify-business-outcome-live.py` PASSes — commit/push ≠ live.

## Phase 5

Deferred until Phases 1–4 **live-verified on tip** (presentation-only; DTO contract frozen; re-verify after restyle).

## Verification

- Unit: `pytest backend/tests/services/test_business_outcome.py` — PASS (10)
- Live: **NOT RUN** until Railway tip ≥ BusinessOutcome ship (`docs/delivery/business-outcome-live.json`)
- After token fix: redeploy → confirm `/health` `git_sha` → `python scripts/verify-business-outcome-live.py --expect-sha <tip>`
