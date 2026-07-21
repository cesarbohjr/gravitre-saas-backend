# Part 1 — Pending-reply decision map (baseline tip `5cdc3db7`)

Honest map before the 7-way structural classifier. Pipeline: orphan `current_plan` → platform → orch → connector → clarification → ReAct.

| Pending status | First handler | Recognized | Anything else |
|---|---|---|---|
| `awaiting_params` | connector `process_turn` / resume | slot fill + tip 3-way meta | re-emit Still needed; no ReAct |
| `awaiting_confirm` | connector after params | CONFIRM/DECLINE | restage approval |
| `awaiting_admin_approval` | connector | decline / confirm→queue | restage |
| `awaiting_plan_confirm` | orch (before connector) | confirm/decline/supersede | "Reply yes" reminder |
| `awaiting_step_confirm` | orch | same | step reminder |
| sticky `current_plan` | orphan + prepare 4-way | continue/modify/cancel/unclear | plan sticks on unclear |
| terminal orch | clear/fallthrough | — | clarify/ReAct |
| `executed` connector | plan rebuild | can re-trap | unrelated stuck |

**Root shape:** recognition is local pattern matching per status, not one pending-reply ontology.
