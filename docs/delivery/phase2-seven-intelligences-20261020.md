# Phase 2 — shared seven-capability coordination

Scope confirmed by the user on 2026-10-20: connect sentiment, contextual,
causal, temporal, relational, adaptive and predictive intelligence through the
existing router, shared by text and voice. Baseline: `8c8793c48` on main, which
includes Phase 1 and the existing live-acceptance workflow.

## Implemented

| Capability | Existing implementation reused | Shared decision contribution |
| --- | --- | --- |
| Contextual | `ContextualUnderstandingService` | Goal, constraints, entities and history-derived understanding are carried into reasoning. |
| Sentiment | `SentimentFrictionService` and organization preference | Same perception and closed-set presentation adaptation; no new emotional-certainty claim. |
| Temporal | Understanding's temporal extraction and router retrieval freshness | Existing temporal references and available freshness labels accompany the decision. This does not add a calendar/date-resolution engine. |
| Relational | `KnowledgeGraphService` | Reuses already assembled graph context or requests the existing scoped one-hop entity explanation when an entity is present. Missing entity is explicit. |
| Causal | `load_causal_enrichment_context` | Existing measured-outcome attribution retains its correlational/insufficient-data disclosure; never relabelled causal proof. |
| Adaptive | `AdaptiveLearningService`, org opt-in and `LearningConfidenceService` | Reads existing segment state only for relevant requests. Sample gate, disabled state and missing evidence remain explicit. No updates or training are performed by coordination. |
| Predictive | `PredictiveOperationsEngine` and existing model catalog | Requests actual domain predictions with existing artifact/features/data checks. Model selection alone is no longer represented as a prediction. Unsupported domains and insufficient data are explicit. |

`IntelligenceRouter._run_enrichments` is the common coordination point. Its
seven-slot `capabilities` envelope includes source, status, bounded evidence and
advisory-only labels. Optional providers run concurrently with individual
1.5-second await deadlines. Timeout/provider errors remain visible in the
envelope rather than silently disappearing. Cancelling an awaited blocking read
does not terminate a socket already running in the existing I/O pool.

The existing chat facade delegates to this same router. `AgentIntelligence`
passes shared perception through it for typed and spoken turns and carries the
result to unified LIVE/shadow and classical generation. Relevant intelligence
is included as fenced evidence; markup delimiters are escaped and each slot is
bounded. It grants no authority and does not alter approval or tool permissions.
Capability statuses are included in existing routing metadata, including voice.

Conversational/compiled shortcuts retain the seven-slot contract while deferring
optional reads. Absence, disabled, insufficient, deferred and unavailable states
are not presented as successful intelligence or negative business findings.

Existing synchronous graph, catalog-count, adaptive-state and causal snapshot
reads used by these providers now use the established I/O pool so they do not
hold the voice event loop. There are no new engines, model families, registries,
database tables, migrations or production configuration changes.

## Validation

Initial focused run: **100 passed**, including router/facade integration and
actual captured typed/spoken model-call prompt assertions. The broader regression
run passed **1,746 tests with zero failures/errors/skips**, including the complete
Pipecat directory, simulated voice scenarios, operator integration, text/voice
execution parity, graph, prediction, adaptive, attribution and catalog tests.
After the final optional-read relevance gate and invalid-result/prompt-size
guards, **48 focused tests passed** on the final code. The typed normal-turn,
spoken plan-hold and approval-no-provider regression subset also passed
(9 tests with the coordinator contracts). Compilation and `git diff --check`
passed. These are separate, overlapping runs, not 1,903 distinct tests. Tests use
`-p tests.offline_network_guard`; sockets/DNS are blocked and providers scripted.

New contracts cover all seven contributions, graph reuse, organization arguments,
prediction execution rather than selection, adaptive opt-in/sample gates,
timeout cancellation, isolated provider failures, prompt fencing and shortcuts.

## Retained engineering sequence

1. Audit the 14 existing models (Phase 1).
2. Connect seven capabilities through the existing router (this change).
3. Run the 12-point text/voice audit with real scenarios and measurements.
4. Repair verified deficiencies using existing components.
5. Validate approved actions, independent readbacks, later measured outcomes and
   subsequent decision improvement.
6. Run release gates, deploy approved changes and repeat live acceptance.

The 12 audit requirements remain intent, contextual memory, sentiment, reasoning
and causality, temporal/relational intelligence, predictive/adaptive intelligence,
response quality, text performance, voice performance, connector execution,
governance/accountability, and end-to-end learning. This Phase 2 wiring is not
evidence that all 12 meet acceptance or that any trained model improved.

Comparable ChatGPT/Claude benchmarks, real mic-to-speaker acceptance, latency
and complete learning-cycle proof belong to the subsequent phases. No subjective
parity score or production PASS is asserted here. Full standing LLM batteries
are required before accepting this prompt change in a release; this workspace
does not have the authenticated battery credentials. Do not substitute unit
tests or the earlier Phase 1 chat smoke for those results.

## Compatibility refresh after model inventory and consent merges

Resolved the catalog conflict against main `34015a81dfa91bd8bd1c04616ac7a2f6add91e85` by retaining both the advanced-artifact model set introduced in #522 and the established I/O-pool dispatch from Phase 2. The router's automatic merge preserves #522's catalog-input extension and the same consent-enforcing loader. New integration regressions check that inactive consent blocks world-model inference through the shared seven-capability router and that advanced-artifact status reads remain off the event loop.

The broader regression run identified stale world-model tests on main that patched a removed observation-count method. These now exercise all four combinations of artifact loading and reviewed consent, plus the absence of predictions when an artifact is missing. This strengthens the current readiness contract; it does not relax promotion or consent requirements.

Local offline verification also exposed a test-containment gap: Python socket interception does not prevent C-backed gRPC channel creation by legacy provider SDKs. The opt-in offline test plugin now blocks HTTP transport dispatch and synchronous/asynchronous gRPC channel factories as well. The contained local run uses explicit fake provider credentials; these safeguards do not modify production networking or provider behavior. A local test action was rejected by automatic approval review when it attempted a Google Generative Language request; that run is not accepted as passing evidence. The stronger containment is a safer test alternative, not authorization for live provider calls.

Focused coordinator/unified/model-consent tests: 71 passed. ML suite: 141 passed. Contained agent-streaming and updated world-model compatibility suite: 67 passed. These runs overlap. Full refreshed CI and the final broader contained-regression results are reported on PR #520. Production acceptance and the standing live LLM batteries remain distinct from these unit and simulated checks; no live quality, latency or improvement claim is made here.
