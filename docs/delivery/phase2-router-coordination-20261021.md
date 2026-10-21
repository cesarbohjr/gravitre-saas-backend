# Phase 2: seven intelligence capabilities through the existing router

User-confirmed scope: coordinate sentiment, contextual, causal, temporal,
relational, adaptive and predictive intelligence through the existing router.
This follow-up starts from the released #528 implementation. It retains the
existing six-phase engineering sequence and does not introduce new engines.

## Coordination changes

| Capability | Existing component and coordination behavior |
| --- | --- |
| Contextual | Reuses the turn's contextual understanding and history-derived goal/constraints. Catalog intent, domain, embedding, planning and symbolic advice reaches this slot when supplied by an authorized backend caller. |
| Sentiment | Reuses the same perception result for typed and spoken turns. An organization that disables sentiment detection now has an explicit disabled slot, rather than an available-looking neutral result. |
| Causal | Retains existing outcome attribution/paired observational analysis and its non-causal limitations. Catalog causal evidence belongs here, preserving service disclosures. No claim of controlled causal identification. |
| Temporal | Carries actual extracted references and supplied retrieval freshness. Empty references plus absent freshness are not marked available. No new date resolver or calendar engine. |
| Relational | Reuses provided graph context or an explicit entity reference. Otherwise resolves the question against existing organization knowledge nodes through the established resolver, then calls existing scoped one-hop graph explanation. No speculative entity-identification LLM call or fabricated ID. Unresolved entities remain explicit. |
| Adaptive | Reuses the opted-in segment state and confidence/sample gates for relevant department/retrieval/enrichment requests. Ranker, retrieval composition, recommendation ranking and meta/active-learning catalog advice belongs here. Coordination performs no learning updates or training. |
| Predictive | Calls the existing domain prediction engine for both string and structured department classifications. A failed model no longer erases successful siblings. Preserves valid domain predictions when an unrelated catalog model falls back. |

All seven slots remain advisory and use the existing fenced, bounded evidence
format. Existing catalog artifacts, features and current-consent guards remain
authoritative. Catalog TRAINED alone is never inference proof. This change maps
supplied catalog evidence to its semantic consumer; it does not automatically
fabricate feature inputs for all 26 models or run them on every utterance.

The shared chat facade delegates to this same router. Existing unified LIVE/shadow
and classical generation paths consume the envelope. Shared perception now
tags disabled sentiment at its source so every existing caller preserves it. No alternate text
or voice coordinator is created.

Deferred spoken/compiled shortcuts now skip **all** optional graph, causal,
predictive, adaptive and catalog calls. Relevant deferred capabilities remain
visible as deferred, not active. Already supplied perception/graph data can still
be reused. Optional calls retain their concurrent 1.5-second deadlines and
isolated failures. A catalog timeout remains attached to the requested model
and correct capability instead of becoming anonymous pseudo-model metadata.
Cancelling an await does not terminate a blocking socket already in the existing
I/O pool.

## Verification and release boundary

Focused checks: **90 passed**. Expanded coordinator/facade/unified-turn/ML checks:
**300 passed, 4 skipped**; optional Flower dependencies are absent locally.
These selections overlap. Tests block HTTP transports, Python sockets/DNS and
gRPC, and use fake provider credentials. The first expanded run found a missing
local SOCKS transport package; installing that test-environment dependency fixed
the three setup failures without changing repository requirements or assertions.

New tests verify all seven contributions in actual captured unified-turn model
calls for both typed and spoken modes, a real trained/save-loaded IsolationForest
prediction flowing through the existing domain engine and router, consent-bound
input collection, scoped graph resolution, catalog semantic consumers, preserved
uncertainty/fallbacks, disabled sentiment, empty temporal evidence and deferred
zero-provider behavior. Synthetic local data is not production inference proof.

The existing graph-evidence regression now uses a non-deferred turn and requires
the relational slot, rather than predictive. The former fixture demanded model
execution while optional work was deferred and classified graph inference as
predictive. Separate new negative tests require zero optional calls on a
deferred turn. No assertion is relaxed to hide an unavailable runtime.

Broader regression and CI results will be recorded on the pull request. No
database migration, new dependency, customer-facing toggle/price, production
setting, tenant permission, model training or provider operation is introduced.

**Live release acceptance is still required.** This changes evidence reaching
generation, so `docs/ENGINEERING_STANDARDS.md` §8 applies: “Re-run the **full
combined battery** after any change to Module D voice spec, unified-turn prompt
assembly, or task model tier — not ad hoc spot checks only.” The standing scripts
are listed in `docs/delivery/llm-quality-test-suite.md`. The available GitHub
connector cannot dispatch the credential-backed workflow. Production quality,
real microphone-to-speaker behavior, latency targets and learning/outcome
improvement must not be marked PASS from these offline tests.
