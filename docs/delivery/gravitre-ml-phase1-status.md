# Gravitre ML program: Phase 1 execution status

Baseline: the user's recovered six-phase engineering sequence, explicitly supplied on October 20, 2026. This file records that sequence and implementation status; it does not replace it with another roadmap. Resume from this file and the linked delivery report after a context reset.

## Agreed sequence

| Phase | Scope | Acceptance status |
|---|---|---|
| 1 | Audit the 14 existing models; implementation and readiness across all 26 catalog entries, artifacts, inference, fallbacks, data eligibility and consent-controlled activation | OPEN |
| 2 | Coordinate contextual, sentiment, causal, temporal, relational, adaptive and predictive intelligence through the existing core/router; prove real model outputs reach relevant backend consumers | OPEN; #520 is infrastructure, not completion proof |
| 3 | Complete the 12-point text/voice experience audit with real scenarios | Not started by this batch |
| 4 | Repair verified experience deficiencies using existing components | Follows Phase 3 findings |
| 5 | Validate approvals, independent readbacks, measured outcomes and repeat-turn improvement | Not claimed from model tests or execution logs |
| 6 | Release approved changes, CI, deployment alignment and live acceptance | Not complete for this program |

The Phase 3 acceptance areas remain: intent understanding; contextual memory; sentiment/emotional intelligence; reasoning/causal intelligence; temporal/relational intelligence; predictive/adaptive intelligence; response quality; text performance; voice performance; tools/connectors; governance/accountability; end-to-end learning validation. No microphone, frontend redesign, voice-parity testing or new continuous-learning initiative is part of the current batch.

## Foundations retained

- #520: shared seven-intelligence coordination, merged; full integration not proven.
- #521: honest inventory separation and readiness reporting.
- #522: versioned training consent and bounded advanced algorithms.
- #528: graph convolution, organization-local Reptile, automatic bound-corpus training, workflow feature/inference repairs, RAG consent repair and diagnostic inference API. Original head `23f51cfd2128bc0e6e4ecc983e44d0b3c48feaa6` passed [CI 39510942362](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39510942362). That success does not cover subsequent commits.

## Current Phase 1 batch

1. **SLA and deal models have working data adapters**, replacing permanent `missing_training_columns` responses. Reuses existing bound organization training records, canonical model classes, artifact registry and promotion gates. Never treats ticket volume as an SLA-breach label or aggregate revenue changes as per-deal won/lost labels.
2. **Their inference consumes every supplied real row**, instead of ignoring `X` and scoring an empty feature map. Missing/incomplete, nonnumeric and nonfinite feature rows fail closed. Empty/unfitted artifacts cannot count as loaded valid risk models.
3. **Temporal validation and calibration**: features must predate resolved outcomes; entity identifiers are distinct; labels unavailable before the final holdout observations or a calibration window are purged from that training partition. Delayed but valid outcomes do not permanently block activation; sufficient resolved history is still required. Both classes are required in training, calibration and holdout. Sigmoid calibration uses time-series folds inside the training window; final holdout stays untouched. AUC must beat chance and held-out log loss must beat a prior baseline. Brier/log loss are reported, not claimed as independent proof of business improvement or perfect calibration. Training runs off the request event loop.
4. **All 14 core entries are consent-managed**, including the newly usable SLA/deal trainers. The complementary reconciler now handles 11 entries; the existing company-learning steps cover the remaining eight consent-managed entries, including the retrieval composition over its existing components. These are 19 consent-managed catalog entries total, not 19 independent engines or duplicated training jobs.
5. **Retrieval composition uses its deployed ranker**, not summary counts masquerading as predictions. It reuses the same artifact/version, requires wrapper and ranker permission, and does not create another trained-model artifact. Composite training also requires component permissions before reading/training.
6. **New imports are considered**: bound-corpus discovery examines the latest 1,000-record window and restores source order for downstream validation. Older records cannot permanently hide new qualifying data. Discovery uses metadata only. Training rechecks actual contents and temporal validity.
7. **Current consent is checked before manual Temporal enqueue**, including the shared starter used by other callers. Readiness counters use the new labeled-record source, and draft registry rows no longer masquerade as recently trained models. Approval, pause/revoke and all actual trainer/loader guards remain in force. No consent is granted by this work.
8. **Execution evidence uses the existing prediction ledger**: deployed-artifact calls through the shared boundary store only generated trace ID, organization/model/version, source, timing and proof type. No customer input or model output is stored by this added evidence mechanism. Diagnostic calls do not count as normal backend use. Ledger I/O is offloaded and time-bounded; failures do not convert a usable prediction into a fallback. Evidence readers ignore missing/legacy/expired proof, match the currently loaded model/version, and explicitly do not claim downstream consumption or outcomes. Dashboard `inference_health` remains unverified; recent execution evidence is separate.
9. **All 26 lifecycle contracts are explicit** through the admin-only `/api/admin/ml/lifecycle`. Nineteen are organization-trained/composed, three are on-demand advisory algorithms, and four have specialized engineering/infrastructure blockers. Unknown data/permission reads never become zero-data or active claims. A paused/revoked model cannot become active from a stale execution record.

## Risk-data contract

Existing model binding: `purpose=training`, organization-scoped model target, metadata `schema_version=1`, `model_name`, one consistent `target_definition`: exactly `sla_breached` or `deal_lost` for the respective risk model (positive label `1` means breached/lost). Other targets cannot silently train those named models. Record metadata declares `synthetic=false`, `label_source=human_reviewed`, nonempty `source_ref`. These are provenance declarations, not independent source verification.

Each record's JSON input contains `entity_id`, complete numeric `features`, timezone-bearing `observed_at` and `outcome_observed_at`. `expected_output` is exactly `0` or `1`. SLA features are `open_tickets`, `avg_resolution_hours`, `backlog_ratio`, `weekend_load`, `escalation_rate`; deal features are `deal_stage_index`, `days_in_stage`, `deal_amount`, `engagement_score`, `activity_count`. Features must be available as of their observation timestamp, not reconstructed using outcome information. Minimum 60 SLA / 25 deal records; minimum counts alone do not establish eligibility. Invalid chronology or calibration/holdout coverage blocks training. Connector-derived historical feature ingestion and independent source-reference readbacks remain prerequisites for claiming production readiness of an actual organization's data.

## Remaining Phase 1 acceptance work

**Phase 1 and Phase 2 remain OPEN.** The following are not completed by this batch:

- Actual eligible organization data, current administrator consent, deployed artifacts and real inference for every applicable model. No production approvals/training/promotions were performed.
- Federated learning: actual legal/customer authorization, deployed runtime, audited secure aggregation, validated DP/accounting and participant threshold. Still blocked; plain aggregation was not substituted for a privacy protocol.
- Diffusion: governed paid provider/tool execution, security and generated-asset handling remain engineering gaps.
- Multimodal: full provider execution and media validation remain engineering gaps; existing image selection alone is insufficient.
- Domain-specific LLM: approved departmental corpus, independent evaluation and catalog training/routing integration remain engineering gaps; existing agent fine-tuning is not automatically catalog readiness.
- Further advanced input assembly: active-learning review integration, vetted rules/facts, controlled causal identification, authorized action candidates, graph/context assembly and independent local-embedding retrieval evaluation remain incomplete.
- Existing on-demand/dedicated model consumers do not all use the common execution ledger. A zero-log observation is absence of evidence, not proof no inference occurred. New common-boundary evidence proves execution only, not all seven intelligence consumers or frontend use.
- Production SHA alignment, authenticated activation/pause/resume acceptance, independent inference traces and a complete phase closure review. Passing CI is necessary and insufficient.

Earlier production observations are historical: see [the October 20 readiness audit](ml-readiness-and-advanced-engineering-20261020.md) for its exact SHA/time, two deployed pointers and absent consent/prediction rows. Do not present that snapshot as a fresh production measurement.

## Validation

Initial targeted tests: **45 passed** before final guards/refinements. Broad backend service/ML/lint/intelligence regression after the risk and queue changes: **7,778 passed, 2 skipped** in 188.46 seconds. Final targeted tests after the last refinements: **109 passed, 1 skipped** (native PostgreSQL server binaries unavailable; the actual migration separately passed isolated PGlite checks). Provider HTTP/socket/gRPC dispatch is blocked and provider credentials are fake/empty for local tests. No production customer data is used in synthetic algorithm tests.

The existing unsupported-trainer regression now asserts denial before data access without current consent; it no longer asserts a permanent missing-columns response because real bound-data pipelines exist. Inventory fixtures now require real support for SLA/deal training and retain exact rejection assertions for unsupported models. These changes reflect newly implemented behavior, not weaker data/consent/evaluation gates.


## Production registry schema blocker discovered read-only

A read-only production constraint query on `public.trained_models` confirmed `trained_models_model_type_check` permits only classifier, fine_tuned_llm, anomaly_detector, forecaster and embedding. It rejects the existing runtime enum's `regressor` and `causal_model`. The bounded world model uses `regressor`, so successful Python training is insufficient: production registration would fail.

Prepared migration: `supabase/migrations/20261020234133_ml_registry_model_type_compatibility.sql`, generated using the official Supabase CLI's `migration new`. It changes only this existing type constraint to the seven `ModelType` values. It does not add `trained` to registry statuses, change data/pointers, broaden grants, change RLS, or grant consent. The status constraint still rejects the catalog's `TRAINED` designation as a runtime registry state.

Verified the actual SQL on a separate embedded PostgreSQL engine (PGlite): the old constraint rejects regressor; the migration admits all seven types; unknown types and runtime status `trained` remain rejected; existing rows and enabled RLS remain unchanged. A native PostgreSQL regression using the repository's throwaway-cluster harness is committed; it skips locally when server binaries are unavailable. This is not a production migration test or evidence that production registration now works.

**NOT APPLIED to production.** The user has now explicitly authorized migration, commit, push, merge and deployment **after advanced-model gaps are fully integrated and resolved**. That condition is not yet met. Release authorization does not grant organization training consent, provider data-processing consent or cross-tenant federation permission. The world-model lifecycle contract continues to report the prerequisite migration and unverified deployment state.


## Release follow-up: October 20, 2026 (Vancouver)

The latest published head `8b16a9b0b4ea4da318ce6d6520d8568c7489abb4` failed [CI 39517222617](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39517222617): 11,799 backend tests passed and one migration test failed because it called `Pg.sql`, which does not exist. The test now uses the actual harness `psql`/`value` methods without relaxing its database assertions. Web, dependency audit, shared text/voice gate, migration safety and SEO guard passed on that published head. These results do not establish CI success for the follow-up changes.

Additional verified gaps repaired in this follow-up:

- The shared registry deployment method now checks current catalog training permission, champion/challenger evaluation, a positive version and an artifact reference. This covers both manual HTTP deployment and direct registry callers. A rejected manual promotion returns HTTP 409 instead of writing the deployed pointer. This is a promotion gate, not proof that the referenced artifact has loaded or served inference.
- Graph artifacts now persist the target definition and ordered feature names in schema version 2. Inference refuses equal-width inputs with different feature semantics or targets. Bound training takes the target definition from the administrator's dataset binding, overriding any conflicting input field. Champion comparisons reject different graph targets/schemas even when their scalar AUC improves. Legacy schema-1 graph artifacts fail closed and require retraining with the declared semantics; they cannot be silently upgraded by guessing names.
- Agent fine-tune resolution no longer falls back from an absent deployed pointer to `current_version`. Assignment of an unpromoted artifact leaves the existing base-model inference path in place. A valid deployed champion can still serve while a newer challenger is registered.

Validation: **383 passed** in the expanded model/lint/agent regression; final focused follow-up checks **49 passed, 1 skipped** with provider dispatch blocked and fake credentials. The native PostgreSQL migration test is skipped locally because server binaries are absent and package installation is unavailable in this environment; its corrected harness calls must run in CI. Earlier embedded PostgreSQL verification remains historical evidence, not a substitute for that CI check.

**Release condition remains unmet.** The four specialized advanced entries remain scaffolds: multimodal provider/media execution, domain fine-tuning corpus/evaluation/catalog integration, governed image generation with asset handling, and federated runtime/privacy protocols. Real backend input assembly and consumer proof for the other bounded advanced capabilities also remain incomplete. No production migration, merge or deployment is claimed by this follow-up, and no organization consent is granted. Do not convert these engineering gaps to `TRAINED` or call the advanced-model program complete from the passing regression tests.


## Advanced execution implementation — October 21, 2026 UTC

The four specialized entries now have concrete execution code, retaining their original catalog identities and existing intelligence/training/tool boundaries. This supersedes the preceding four-scaffold implementation assessment, **not** the open Phase 1/2 live-verification status.

- Multimodal: bounded real image/audio/video decoding; existing Deepgram transcription and native ModelRouter image blocks; purpose-specific consent, model policy and durable reviewed provider budget; no caller URL fetch or speculative media processing. Video reports sampled-frame/transcript scope. Backend image installs ffmpeg.
- Domain training: existing bound-data/queue/worker/registry lifecycle; declared departmental classification; at least 1,000 reviewed training examples and 100 disjoint benchmark examples; exact label/model verification, same-holdout base/champion comparison and gated promotion. Provider dispatch and corpus identity are checkpointed durably. This does not implement arbitrary free-form expert adaptation or prove provider account eligibility.
- Governed image generation: native canonical WRITE action, explicit human/approved-run authority, paid-provider consent, durable organization budget, duplicate/uncertain-dispatch protection, private actual-storage checks, bounded PNG decoding, independent checksum readback and existing hosted-file artifacts. It is not speculative enrichment or an automatic paid operation following consent.
- Federation: optional isolated Flower 1.41 SecAgg+ server/client/control deployment; encrypted ranker projection to distinct enrolled tenant keys; Google DP Gaussian sampling, replace-one sensitivity and composed RDP accounting; durable per-tenant expenditure and round identity; mTLS control plane; metadata-only consent callback; source run-ID reconciliation after restart. No source database or artifact master keys enter Flower containers. Exactly 100 distinct approved tenants are required. Aggregate output remains a candidate, not a promoted model.
- Backend: actual workflow candidates/outcomes and vetted rule facts reach the existing common planning/world/neurosymbolic inference boundary. Media/domain tools reuse the existing shared tool registry; image generation uses the audited write spine. Existing core models and seven-intelligence core remain in place. Added evidence records execution, not proven downstream outcomes.
- Intelligence approval dialog differentiates training, media processing, generation and cross-tenant private updates. Planned/disabled entries without real detected eligibility/request remain out of ordinary customer controls. Catalog TRAINED still never establishes loaded artifacts or healthy inference.

Verification: 339 ML/lint tests passed; final specialized execution/runtime checks 45 passed, followed by 7 runtime tests after restart-readback refinements. Actual Flower bundle build passed after correcting SDK imports, bounded bundle entrypoints and deployment naming. Web full suite previously passed 297 files / 1,894 tests on this implementation; final TypeScript check passed. All local provider traffic blocked and credentials fake/empty. Broad backend regression and fresh remote CI remain pending final recorded results.

**Release remains incomplete.** There has been no live paid-provider call, trained tenant artifact, independent privacy review, deployed authenticated Flower fleet, 100-tenant consent cohort, federated per-organization adoption evaluation, or production inference/consumer outcome proof in this batch. Additional source assembly and consumer acceptance across the broader advanced catalog remain unverified. Main advanced independently to 67dc426aeeb3b5d618159706c78c005275765289 during this work and must be incorporated before final CI/release. Migration/release authorization persists; no organization/provider/federation consent is implied. No production migration, merge or deployment is claimed.


### Current-main integration and action contracts

Current main 67dc426aeeb3b5d618159706c78c005275765289 was incorporated without conflicts, retaining its billing and Trust & Safety changes. Image generation is represented as a platform action consistently in the execution matrix, preventing an automatically generated `assistant_` alias from bypassing write approval. Canonical output/enrichment/verification declarations now include the new action. The completion mapper requires status, artifact verification, checksum, private storage path and attached artifact before stating completion; generic follow-up classification stays conservative. Current permission is rechecked before each domain inference dispatch.

Combined-main frontend validation: **297 files / 1,896 tests passed**, TypeScript passed. Broad backend failures found the new action's missing canonical declarations and the earlier Flower import issue; these were repaired in implementation rather than bypassed in tests. Fresh broad and focused combined-main results are pending. The React skill checklist found no additional hook, state-isolation, accessibility or bundle changes required for this dialog patch. Customer-facing consent/permission behavior was explicitly requested by the user; no customer price or unrequested activation toggle is introduced.


Final focused combined-main regression: **742 passed** across ML, lint, action output/enrichment contracts, write-approval catalog coverage, success-verification declarations and current-main SIEM filtering. Frontend lint: zero errors, four pre-existing unused type-import warnings in `lib/api.ts`. These are synthetic/offline results, not production acceptance. Broader service regression and remote CI remain pending.
