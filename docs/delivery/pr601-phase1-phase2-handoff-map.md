# PR601 — Phase 1 integration map and Phase 2 failure-boundary analysis

Evidence: direct inspection of branch `audit/601-conversational-runtime-reconciliation`, November 2 production observations previously recorded in PR601 audit documents. This is a source-level checkpoint, not live regression certification.

## Phase 1: verified source handoffs

| Producer | Consumer | Observed contract | Status |
|---|---|---|---|
| Voice cognitive LLM (`backend/app/services/pipecat_voice/cognitive_llm.py`) | Unified turn service | Medium/deep tiers and live reasoning entry points exist | Wired in source; turn-level success not proven |
| Unified turn live | `run_unified_turn_shadow` | Passes conversation_history, task_state, agent, permitted_tools, classification, reasoning_depth, cognitive_context, response_style_key and conversation_tier | Confirmed in source |
| Unified turn model resolution | `MODEL_TIERS` and provider tool router | Uses preferred_ai_provider; explicit voice conversational override can select a different model/provider | Confirmed; effective override and credential health unverified |
| Unified turn preflight | `provider_tools_configured` | Checks the **resolved model's** provider before call | Confirmed; preflight is not an authenticated inference |
| Unified turn model exception | `UnifiedTurnShadowResult(outcome_kind="error")` | Catches all exceptions, logs error and returns error result | Confirmed |
| Live unified turn error | Classical fallback caller | On skipped/error marks fallthrough, audits and returns None | Confirmed; actual caller recovery not traced |
| Agent selector | Persona prompts/manifest | Role and persona selection code exists | Source present; final prompt and voice response effect unverified |
| Intelligence router | Downstream reasoning | Seven capability definitions and enrichment logic exist | Source present; invocation and consumption unverified |
| Intent gateway | Connector discovery | Gateway handles connector-related replies | Source present; authorized execution from inventory unverified |
| Production deployment | PR600 | PR600 is draft, not included in deployed main SHA | Not deployed; avoid duplicate repair |

## Phase 2: concrete defect boundary

1. `_resolve_model` selects a provider-family model from preferred_ai_provider and tiers; `voice_conversational_model` may explicitly override this. **Provider selection is not credential authentication.**
2. `run_unified_turn_shadow` preflights configuration with `provider_tools_configured`, but production inference still emitted HTTP 401 invalid key. A configured key can be invalid.
3. Around model-call exception handling, a broad exception becomes `outcome_kind="error"`; no second-provider retry is visible **inside this exception handler**.
4. In `run_unified_turn_live`, `error`/ `skipped` marks fallthrough and returns `None`. This preserves function inputs into the shadow call but does not prove the classical caller retains the task, handles the error accurately, or chooses a healthy alternate provider.
5. An `auth_backoff.py` file was not found at the expected path in the deployed-derived branch. Do not assume that PR600's separate backoff implementation is live.

## Repair specification (implementation pending)
- Establish canonical provider/model eligibility and health policy; honor explicit model overrides, tenant policy, permissions and configured providers.
- Classify authentication 401 distinctly from timeout, transient 429/5xx, and invalid request. Never retry the same invalid credential in a tight loop.
- Select an alternate **only if explicitly allowed and credential-health verified**, preserving immutable task state, history, agent/persona, approvals, tools and trace ID.
- Where failover is disallowed or no healthy provider exists, surface a precise actionable failure rather than a context-loss clarification.
- Avoid fallback into any path that can duplicate already dispatched writes. Respect idempotency journal and authorization.
- Instrument sanitized provider attempts and fallthrough outcome, with no secret or prompt logging.
- Tests: configured-but-invalid preferred key; healthy allowed alternate; no alternate; explicit override disallowing switch; interrupted write; task continuity and multi-turn Outlook request; exact-head CI.

## Next source inspections before safe patch
- Full `_resolve_unified_turn_model` and model dispatch logic (including explicit overrides).
- Classical caller of `run_unified_turn_live`, with task-state ownership and side-effect boundaries.
- Provider router, credentials-health service and existing fallback utilities; avoid creating competing policy.
- PR600 overlapping implementation and tests to prevent code duplication.

Status: Phase 1 **partial mapping complete**; Phase 2 **failure boundary identified, repair not yet implemented or certified**.
