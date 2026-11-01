# PR #581 — Agent manifest → seven-intelligence router contract

**Implementation requirement (not yet verified):** The unified Engineering, QA, Security and Agency agent manifests must be consumed by the existing seven-intelligence coordination route and unified-turn prompt assembly. Do not create a parallel intelligence engine, router, or permission system.

## Integration
1. Resolve the selected agent role using `app.capabilities.agent_manifest.resolve_agent_manifest`; unknown roles fail closed. Preserve the selected tenant, agent identity, authorized task, and scoped context.
2. Include the resolved manifest's role guidance in the bounded agent prompt envelope, alongside—not in place of—the existing seven-capability evidence. Capability tags describe intent and are **never** executable tool grants.
3. Route the same scoped request through the existing contextual, sentiment, causal, temporal, relational, adaptive and predictive coordinator. Each capability must preserve its availability, provenance, consent, confidence and fallback/deferred status.
4. Apply canonical IAM, tenant isolation, connector readiness, human approvals and verified-write controls at execution. An advisory intelligence result must not bypass any gate.
5. Preserve text/voice parity and existing timeouts; never claim a missing or deferred intelligence result ran.

## Acceptance evidence
- Unit tests for role resolution, unknown-role rejection, bounded prompt guidance and absence of permission escalation.
- Integration tests for each of the four roles through the **existing** seven-intelligence route, with all seven evidence slots and explicit missing/deferred states.
- Negative cross-tenant, unauthorized tool, missing consent, missing connector, approval and fallback tests.
- Text-to-text, voice-to-text, text-to-voice and voice-to-voice regression coverage where the unified route is invoked.
- Full combined battery required by `docs/ENGINEERING_STANDARDS.md` section 8 after unified-turn prompt changes; live provider-backed downstream verification remains a separate release gate.

**Status:** Contract recorded; runtime wiring and tests are not yet complete. PR #580 certification remains independently gated.
