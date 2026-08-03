# Browser extension v3 — lightweight workflow triggering

Date: 2026-08-03  
Baseline: v2 on tip `ad90950d`

## Model

Overlay lists active typed workflows, shows progress steps (chat plan-bar shape: `dialogueMode=confirm`, `progressSteps`), stages `awaiting_confirm`, then executes via `_execute_workflow_with_context` (same path as chat / schedules). No parallel workflow runner.

## API

| Method | Path | Role |
|--------|------|------|
| GET | `/api/extension/workflows` | List active workflows + progressSteps |
| POST | `/api/extension/workflows/execute` | Propose (token) or confirm (token → execute) |

## Live proof — PASS (local / pre-tip)

- Workflow: MSP NVD CVE Lookup `ac093988-0c22-55d7-8283-d77a048dddf0` (2 invoke_tool steps)
- run_id `624f3fa2-8872-499e-95d1-37ce9ae6e4a2`
- Both steps completed (`nvd-cve`, `cisa-kev`)
- Outcomes DTO `source=browser_extension`, `lifecycleState=approved`
- https://gravitre.app/outcomes/624f3fa2-8872-499e-95d1-37ce9ae6e4a2

## Tip verify fix (2026-08-03)

First tip confirm on `2cafd118` failed with `asyncio.run() cannot be called from a running event loop` because `/api/extension/workflows/execute` was `async def` while the shared workflow engine uses `asyncio.run()` in step handlers / enqueue. Route changed to sync `def` so FastAPI runs it in a threadpool (no nested loop). Tip re-verify artifacts: `browser-extension-v3-tip-verify.json`.
