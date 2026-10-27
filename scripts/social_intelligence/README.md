# Synthetic social-intelligence generated-response evaluation

`build_bundle.py --output <scratch-path>` freezes the real unified and classical
prompt builders for every current `AGENT_PERSONAS` role in text and voice modes,
and twenty-six synthetic social, emotional, multilingual and continuity scenarios. No organization or
customer records are loaded. The classical builder is called without running
the constructor that initializes routers/DB clients; all prompt methods are real.
Voice settings use source defaults. A clean committed source tree is required by
the evaluator. Revision and source-file digests bind the report to its inputs.

`evaluator.ts` exports `runEvaluation(bundle)`. Run it once in a private Bun
script with `ANTHROPIC_API_KEY` and optionally `SOCIAL_EVAL_MODEL` (only the two
repository-supported Anthropic model IDs are accepted). Railway service-variable
references can supply the credential server-side without exporting its value.
Do not add an HTTP listener or a public domain. No tools, application endpoints,
customer data or write executors are available. The workload has 520 paired
cases: 1,040 generated replies and 520 separate judge calls, with two bounded
workers and at most three attempts on rate limits. No completion/failure restart
loop should be configured. The report's status, not deployment/process exit,
determines success. Missing keys are NOT RUN; invalid/failed judgments are ERROR.

Each text/voice pair is evaluated on eight required boolean criteria. A false
criterion in either channel fails the pair; absent/string/extra criteria fail
schema validation. Cross-channel consistency concerns substantive stance, not
identical words or identical harmless suggestions. Outputs and request IDs are
retained only for these fixed synthetic cases; they are not runtime telemetry.
Evidence is LLM-judged and reviewable, not a human quality certification. This
isolates prompt-generation behavior; it does not certify live ingress, provider
routing, organization policy/RLS, final-write enforcement, TTS/STT or devices.
Existing runtime/security tests and standing live batteries remain separate.

Offline contracts: `node --test scripts/social_intelligence/evaluator.test.ts`
and `pytest backend/tests/services/test_social_intelligence_evaluation_bundle.py`.
These never call a provider. No evaluator answer keys are runtime few-shots.

Guidance preserves message priority: classical kernel context is system context;
unified dialogue interpretation is compiled into user context. The paired-path
offline regression checks this distinction explicitly.
