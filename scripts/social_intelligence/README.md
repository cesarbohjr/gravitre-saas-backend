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

## Durable private Railway results

`railway_runner.ts` performs bounded live inference authentication for Anthropic
and OpenAI, then runs all 520 pairs with Anthropic when its authentication passes.
`build_railway_runner.py` embeds a clean synthetic bundle and the tested modules
into one Brotli-compressed, self-contained Function source using Node's built-in
compression (Node must be available while building). The embedded JSON is
byte-equivalent after decoding; source module SHA-256 hashes identify the harness.
The evaluated prompt revision remains the bundle's commit, independently of the
harness revision. This is source evaluation, not deployed production certification.

The `certification-evidence` private bucket supplies endpoint, bucket, region and
credentials through Railway references using the `EVAL_S3_*` variables. No
application database credentials are needed. The runner has no HTTP listener.
Each invocation uses a new run UUID under `runs/<source-sha>/<run-id>/`.
It writes and reads back an initial RUNNING manifest, individual numbered event
objects and a terminal manifest. Duplicate/inconsistent/incomplete PASS evidence
is rejected; an abort records ERROR when storage is available. Stored RUNNING
is never interpreted as PASS, including if a container is terminated mid-run.

Stored fields are allowlisted: identities, status, counters and boolean rubric
verdicts. Replies, prompts, raw exceptions, provider bodies, credentials, headers
and signed URLs are omitted from these durable diagnostics. Unlike the older
private synthetic reply report, this diagnostic format does not retain replies
for manual response review. Human-readable `EVAL_RESULT`, `EVAL_EVIDENCE_READY`,
`EVAL_DURABLE_COMPLETE` and fixed error messages make progress visible even when
Railway's plain-text viewer omits structured JSON fields. Completion explicitly
sets `production_certified=false`.

Tests: `node --test scripts/social_intelligence/{evaluator,durable_results}.test.ts`
and `python scripts/social_intelligence/test_build_railway_runner.py`.

## Separate generated-history multi-turn baseline

The existing 26 scenarios / 520 paired cases are unchanged. The new
`build_conversation_bundle.py --output <scratch-path>` builds a separate pinned
dataset: 12 three-turn scenarios, ten canonical personas, unified/classical
paths and paired text/voice. This defines 240 paired conversations and 720
turn checkpoints; it does **not** mean any live evaluation has run.

The corpus covers intent retention, corrections, non-repetition, requested
brevity, naturalness, role consistency, uncertainty, attribution, tool choice,
handoff honesty and governance. Its six Marketplace target labels reference
already approved agents; labels grant no role, SKU, connector or permission.
Dialogue and current-session continuity sections come from the real builders.
No reference assistant replies are provided: each channel's actual generated
reply becomes that channel's history for the next turn. Histories reset between
scenarios and personas. The common `generationInput` helper preserves the
existing unified user-context / classical system-context placement.

`runConversationEvaluation(bundle, dependencies)` has no default transport,
credential lookup, deployment or runtime activation. Generation and judging
callbacks must be explicitly supplied by an authorized host. Missing callbacks
are `NOT_RUN`; fixture-mode success is `CONTRACT_PASS`, never generated quality
or production certification. Generated mode requires callback-reported provider
provenance and request IDs, but cannot independently authenticate callbacks or
their claimed receipts. A trusted host must retain provider evidence separately.
No live callback is connected or invoked by this increment.

Each call has an abortable deadline (at most 60 seconds), without automatic
retries. Calls are sequential and bounded to 2,000 turn pairs. A failed turn
does not invent history for later turns; authorization errors stop the suite.
The existing strict eight-criterion judge rubric remains authoritative;
explicit user-requested word limits also gate channel style. No new global
product-quality threshold is invented or silently applied to the old baseline.

Reports bind evaluator version, clean source SHA/file hashes, dataset hash and
baseline-case hash. They include category pass/fail/error counts, negative
security outcomes, measured callback latency, hashed reply/request references
and supplied token usage. Missing usage stays unknown; cost is `null` without
verified pricing. Prompts, replies, raw request IDs and provider exception bodies
are excluded from reports. These diagnostics are not wired to the older durable
520-pair reporter or to Langfuse. Production certification is always false.

Offline contracts:
`node --test scripts/social_intelligence/conversation_evaluator.test.ts` and
`pytest -p tests.offline_network tests/services/test_conversation_evaluation_bundle.py`
(run pytest from `backend`). CI retains the existing evaluator contracts and
adds these tests. Unit tests use injected synthetic callbacks; they verify
harness behavior, not naturalness or live conversational quality.
