# PR 601 — Live / intended / missing capability audit (checkpoint 2026-11-02)

Source of truth: Railway production backend SHA `35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae`, read-only GitHub inspection at that exact ref, and PR file inventories. These statuses distinguish deployed **code** from invoked **behavior**.

| Capability | Intended ownership | Present at production SHA | Demonstrated live behavior | Gap / evidence needed |
|---|---|---|---|---|
| Seven intelligence capabilities: contextual, sentiment, causal, temporal, relational, adaptive, predictive | Existing intelligence router, PR581 integration contract, PR587 shared intelligence | YES: `backend/app/services/intelligence_router.py` declares all seven and 10-stage coordinator | NOT VERIFIED | Per-turn capability evidence, timeout/deferred states, impact on reasoning |
| Agency agent personas and specialist role manifests | PR581 | YES: `backend/app/operators/agent_prompts.py`, `backend/app/services/agent_selector.py`, `backend/app/capabilities/agent_manifest.py` | NOT VERIFIED | Verify persona injection in final unified-turn prompt and voice composer, not just selector metadata |
| Shared memory, DSPy guidance, text/voice intelligence | PR587 | YES: production previously deployed #587 SHA and current main follows it; source files in #587 diff | NOT VERIFIED | Trace actual activation and prompt/evaluation outputs, consent and fallback |
| Native agents, capability catalog and canonical permissions | PR581 | YES: #581 changes include native runtime gateway, agent manifest, connector action catalog, registry and tool service; source present at production SHA | NOT VERIFIED | End-to-end dispatch, connector authorization, verified tool result and response |
| Autonomous workflow planning and governed execution | PR597 | YES: current production commit is #597 main merge | NOT VERIFIED | Durable task lifecycle, execution ownership, approval, resume, idempotency and completion |
| Provider model routing and failover | Existing router and #587 | YES: source contains model selector/router and multi-provider tools; production variable names exist | NOT VERIFIED | Actual provider/credential health, effective values, tier selection, successful fallback |
| Contextual connector discovery/clarification repair and auth backoff improvements | PR600 | NO: #600 is 4 commits ahead of deployed main, 21 changed files | NOT LIVE in production SHA | Integrate and test when PR600 ready; do not claim these fixes already cured live session |
| PR601 cohesion audit and repairs | PR601 | NO: PR601 branch not deployed; documentation only | NOT LIVE | Actual integration fixes, tests and certification still required |
| Voice DSPy/Pipecat/LiveKit and playback behavior | PR587, later #600 diagnostics | PARTIAL: #587 code in main; #600 PCM diagnostic changes absent | NOT VERIFIED | Determine active voice engine, feature flag values, real audio continuity and interruption evidence |

## Source-grounded architecture observations
- PR581 seven-intelligence contract explicitly says role manifests must feed existing intelligence and unified-turn prompt, not a parallel engine; its document historically marked runtime wiring incomplete. Presence of newer source does not itself prove this requirement was fulfilled.
- At deployed SHA, `intelligence_router.py` lists seven capabilities and maps auxiliary ML methods to them.
- At deployed SHA, `agent_selector.py` selects `AGENT_PERSONAS` and resolves an explicit manifest role; `agent_manifest.py` treats role guidance as descriptive, not tool authorization.
- `agent_prompts.py` defines structured personas with expertise, heuristics, constraints, tools and system prompts. Need actual final-prompt consumption evidence.
- Railway production source tracks main/backend; tracing is off. Variable names indicate configuration surface only, not enabled values.

## Priority defect candidates (not yet confirmed)
1. Context/persona/intelligence enrichment may not propagate consistently through unified-turn, provider fallback and spoken response.
2. Connector discovery may terminate in a status reply instead of an authorized action.
3. Runtime provider credential failure may interrupt autonomous task progression.
4. Voice engine and PCM output may differ from intended feature-flagged pipeline.
5. #600 remedies are not yet present in production.

## Certification
DEPLOYED_CODE is not equivalent to ACTIVE, EXECUTED or WORKING. Current verdict **NOT_CERTIFIED**. Need exact runtime flag values (without secrets), turn IDs, tool-call traces, provider error details, front-end hosting SHA, and real voice listening tests. No production changes or paid tests authorized by this audit.
