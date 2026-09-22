# GRAVITRE POST-CONVERGENCE GAP PLAN

**Status:** recommendations only. **Do not implement in the acceptance-audit assignment.**

This is **not** a 3.0 rewrite and **not** Computer Use.

---

## Separate judgments

1. **Convergence program** (P0–P6 + M + P7 freeze) — **not accepted** on live `426fce81`.
2. **Full Section 0 product** — **not accepted** (includes deferred computer, artifacts, physical mic).

---

## P0 — must close before any “program accepted”

| ID | Gap | Recommended next (only) |
|----|-----|-------------------------|
| G-P3 | SAPI PCM still false barge-in; assistant silent | Bind origin on the **pipeline/session object**, not ContextVar. Prove interrupt_events=0 and spoken audio frames >0 on SHA after a later fix. Keep physical mic HUMAN_TEST_PENDING. |
| G-P4 | CEO skips healthy HubSpot/Ads | Make required evidence **execute** sealed READ (or honest pending_auth prose). JIT pin is insufficient. Do not let KB/workflow/status satisfy CEO. |
| G-P1 | LIVE + ReAct still both select tools | Prove one-shot: after `read_tool_classical`, no `agent.react.iteration` model tool-choice unless pending-family/defer/repair. Execute LIVE’s ActionSpec under HMAC. |

## P1

| ID | Gap | Recommended next |
|----|-----|------------------|
| G-P2-obs | Waterfall missing from live audit meta | Emit P2 marks on `runtime.turn_latency.critical_path`. Do not optimize again without a SHA-matched waterfall. |
| G-P2-ttft | HubSpot first text +49.6% vs baseline | After waterfall, pick the actual dominant stage. Canned-literal Composer skip did not move TTFT. Do not weaken HMAC. |
| G-P5 | `workflow_waiting` unwired; child Observation unproven live | Wire Composer from child Observation; live-trace one isolated chat→workflow with parent `plan_id`. |
| G-ledger | Ledger still “pending merge / 0 live” after deploy | Refresh ledger from this audit; do not inherit implementation statuses. |
| G-CI | Four non-required live guards failed on 426fce81 | Triage Voice duplex browser guard vs P3; do not ignore if it shares interrupt path. |
| G-M | No bake-off | Run harness when H7 keys exist; keep prod `low` until H8. |
| G-P6 | No BUSINESS_IMPACT | H11 labeled event then prove `outcome_bias_section`. |

## Deferred Section 0 (vision, not this cycle’s PASS criteria)

- Visible computer/browser execution  
- Richer artifact / campaign factory  
- Physical-mic driving LIVE_PROVEN  
- Cross-device resume (EV-J-008)  

Keep them in the independent product backlog. **APPROVED_SCOPE_EXCEPTION ≠ product acceptance.**

## Explicitly out of this gap program

- Computer Use build  
- 3.0 rewrite  
- Changing production model default  
- Governance / HMAC bypass  
- Operator-org tests  

## Suggested sequence (when Cesar authorizes a **new** implementation program)

1. P3 origin/session barge-in (spoken PCM)  
2. P1 one-shot proven on CEO + sealed deals still skip LIVE  
3. P4 execute required live evidence / honest pending_auth  
4. P2 waterfall then evidence-backed TTFT  
5. P5 live child Observation + Composer  
6. Refresh ledger + isolated closure on the **new** SHA  
7. Only then commission another independent audit  

**READY FOR NEXT PRODUCT PHASE: NO** until P0 gaps above are live-proven on a new SHA.
