# PR 601 — Production deployment reconciliation (2026-11-02, America/Creston)

Evidence: read-only Railway production service/deployment metadata and GitHub branch comparisons. No secret values read.

## Backend production
- Railway project `spirited-communication`, environment `production`, service `gravitre-saas-backend`.
- Latest SUCCESS deployment: `64bab084-c059-46da-841a-3a9d39a04090`, created 2026-11-03 00:33:21 UTC (2026-11-02 16:33:21 PST), source `main`, SHA `35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae`, commit message `Draft: Autonomous Agents full-suite orchestration, governed execution and certification (#597)`.
- Prior SUCCESS deployment: SHA `63016431fb52edcde0385cace5cae3c557399732`, message `Shared intelligence: DSPy guidance, text/voice feedback and governed memory (#587)`; subsequently replaced. Therefore #587's work did reach production.
- Railway backend source uses repo `cesarbohjr/gravitre-saas-backend`, branch `main`, root `/backend`, watch pattern `/backend/**`; `checkSuites=false`. Backend deployment state SUCCESS does not certify runtime health or acceptance.
- Production variable **names** include PREFERRED_AI_PROVIDER, UNIFIED_TURN_LIVE_ENABLED, UNIFIED_TURN_SHADOW_ENABLED, AI_FAILOVER_ENABLED, voice flags, learning flags, OpenAI/Anthropic/Gemini keys and Microsoft 365 credentials. Their **values and activation** were not inspected, so names are not proof of correct configuration.
- Railway tracingEnabled=false, autoInstrumentationEnabled=false. This limits native Railway end-to-end trace evidence.

## PR relationship
- GitHub `main` SHA `35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae` matches the backend production deployment SHA at inspection.
- PR #600 branch `feat/conversational-quality-chatgpt-parity` is 4 commits ahead, 0 behind main, with 21 changed files: **not in deployed main SHA**.
- PR #601 branch `audit/601-conversational-runtime-reconciliation` is ahead of main, and its changed files are documentation only: **not in deployed main SHA**.
- PR #597's commit message identifies the latest deployed main merge, but commit presence alone does not certify autonomous task execution.
- PR #227/#231/#580 were not individually ancestry-verified in this pass. Do not equate a PR title or search result with merge/deployment proof.

## Separate frontend Railway project
- `Gravitre front-end` / `gravitre-saas-interface` has latest Railway deployment FAILED dated April 2026, no live domains listed. This does **not** establish the status of the current frontend, which may be served from Vercel or another platform. Verify actual voice-client hosting before drawing conclusions.

## Consequences and next evidence
1. Production voice failures observed November 2 occurred on backend code that did **not** contain PR #600's connector/clarification/auth-backoff fixes.
2. Existing merged intelligence and autonomous orchestration code was present in the deployed backend; whether flags, model credentials, tool grants, runtime handoffs and personality were actually active remains unverified.
3. Correlate failed voice turn IDs with deployed SHA, active provider, feature flag values and tool execution outcomes without exposing secrets.
4. Audit Vercel frontend deployment SHA and runtime, exact PR ancestry, and acceptance workflow results.
5. Keep PR #601 draft, no deployment or paid-provider calls; status NOT_CERTIFIED.
