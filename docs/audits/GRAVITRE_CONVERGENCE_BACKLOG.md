# GRAVITRE CONVERGENCE BACKLOG

**This is the only implementation backlog.**  
**H0 approved 2026-09-22** (binding amendments applied). Execute this list continuously. Isolated org `f07e57c0-…` only. No Computer Use / 3.0 rewrite.  
Progress: `docs/delivery/GRAVITRE_CONVERGENCE_EXECUTION_LEDGER.md`.

Skip any item that does not improve a named Section 0 behavior.

| ID | Phase | Title | Section 0 | Blocked by | Parallel | Reuses |
|----|-------|-------|-----------|------------|----------|--------|
| B0.1 | P0 | HubSpot sealed READ regression on current `/health` SHA | 0.5, 0.11 | — | M | live-read gate |
| B0.2 | P0 | Update release pair on each backend or prod frontend deploy | maintainability | — | all | Railway, Vercel |
| B0.3 | P0 | Frontend SHA descendant of backend or documented exception | maintainability | B0.2 | — | git merge-base |
| B1.1 | P1 | Sealed/compiled READ skips LIVE model | 0.4, 0.9 | P0 | M | sealed_read_execution |
| B1.2 | P1 | LIVE cannot execute proposal → one-shot classical, no second tool-choice | 0.4, 0.9 | B1.1 | M | fallthrough enum |
| B1.3 | P1 | Keep pending-family, defer-SSE, bounded repair | 0.4, 0.5 | B1.2 | — | existing reasons |
| B1.4 | P1 | CEO-prompt dual-select acceptance | 0.1, 0.4 | B1.2 | P4 | evidence-closure script |
| B2.1 | P2 | Instrument sealed READ stage marks | 0.9 | P0 | P1, M | turn_latency_trace |
| B2.2 | P2 | Publish waterfall JSON; **stop** | 0.9 | B2.1 | — | isolated HubSpot |
| B2.3 | P2 | Evidence-backed optimize in P2 bounds (no Cesar H13 stop) | 0.2, 0.9 | B2.2 | — | marks |
| B3.1 | P3 | Audio origin + turn-state on interrupt path | 0.3 | P0 | M | interrupt_reporter |
| B3.1a | P3 | Unit: probe_pcm does not fake barge-in | 0.3 | B3.1 | — | tests |
| B3.1b | P3 | Unit: user_mic during speaking still interrupts | 0.3 | B3.1 | — | tests |
| B3.2 | P3 | Live SAPI PCM speaks or spoken shortcut | 0.3 | B3.1 | — | pcm-closure |
| B4.1 | P4 | Capability evidence plan before JIT/KF | 0.1, 0.5, 0.10 | P1 | M | recipes |
| B4.2 | P4 | KF supplemental; internals not substitutes | 0.5, 0.10 | B4.1 | — | KF retrieve |
| B4.3 | P4 | Honest pending_auth when GA/GSC required | 0.2, 0.5 | B4.1 | H2, H3 | Composer |
| B5.1 | P5 | Live-trace workflow child vs parent plan_id | 0.7, 0.8 | P0 | P1 | handlers |
| B5.2 | P5 | Canonical Observation; no HMAC bypass | 0.5, 0.8 | B5.1 | — | ActionSpec |
| B5.3 | P5 | Composer narrates waiting-user workflow | 0.2, 0.7 | B5.2 | — | Composer |
| B6.1 | P6 | TOOL_SUCCESS is not plan bias | 0.5, 0.10 | P0 | — | outcome_learning |
| B6.2 | P6 | Consume one labeled BUSINESS_IMPACT event | 0.10 | B6.1 + H11 | P4 | outcome_bias_section |
| B7.1 | P7 | Computer strategy freeze; no build tickets | 0.6, 0.7 | — | — | computer eval (design) |
| M.1 | M | Eval keys / scoring harness | 0.2, 0.9 | H7 | P1–P4 | model-tier script |
| M.2 | M | Eval classes n≥5 | 0.2, 0.9 | M.1 | — | MODEL_TIERS |
| M.3 | M | Signed recommendation; prod default unchanged | 0.12 | M.2 + H8 | — | health flag |

**Stop-the-line:** HubSpot 25-deal canned FAIL; WRITE without PendingAction; operator-org writes; invented prices/badges; any new parallel intelligence product.
