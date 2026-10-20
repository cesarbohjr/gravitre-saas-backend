# ML readiness audit and bounded advanced-model engineering — 2026-10-20

## Production evidence and limits

Production is **NOT VERIFIED for all 14 existing models**. Read-only evidence:

- `GET https://api.gravitre.app/health` at `2026-10-20T22:36:12.053466+00:00` returned healthy database/cache and deployed SHA `34015a81dfa91bd8bd1c04616ac7a2f6add91e85`. Main was `f149eca7648db932033a1c9e58321332fa2b8c11`. Thus merged #520 was not yet verified deployed. This work does not change deployment configuration.
- Supabase project `smyeexlrqdpymwjmgzqu`: aggregate, read-only queries against actual production tables found **two deployed pointers** (one churn, one collaborative-filtering), **four artifact versions/pointers**, **zero `model_predictions` records**, **zero model training bindings**, and **no `model_training_consents` records** in organization settings.
- Older `company-workflow-anomaly` and `company-workflow-duration-forecast` entries have no deployed pointers. The current canonical registry uses `catalog-*` workflow names. Old records were not silently promoted or renamed.
- Registry pointers and nonempty URLs are not artifact-load or inference proof. Zero prediction logs are absence of recorded evidence, not proof no model ever ran: several domain consumers do not write `model_predictions`. No customer inputs, artifact URLs, organization identifiers, or raw prediction content were retrieved in the aggregate audit.
- No authenticated production inference was run, no consent was granted, no model was trained/promoted in production, and no migrations were applied. With no recorded consent, the currently managed paths should remain dormant. Model accuracy, realized outcomes, text/voice quality and all-surface production acceptance remain **NOT RUN**.

## Existing 14 models: backend and surface wiring

This is a code-path audit, not a declaration that artifacts are loaded in production.

| Catalog model | Backend consumer / surface | Readiness and remaining limitation |
|---|---|---|
| intent_classifier | `TaskClassifier` → shared text/voice intelligence routing | Deployed, readable artifact and current consent required; rule classifier fallback. |
| workflow_anomaly_detector | Company-learning summaries; predictive domain packs → business signals and shared router | This change adds actual observed-run features and the common inference boundary instead of calling a missing structured method. No canonical deployed pointer in audit. |
| workflow_duration_forecaster | Company-learning summaries; predictive domain packs | Same repair. Scores explicitly identified observed runs; not represented as future-run forecasts. Missing duration is no longer manufactured as zero. |
| workflow_success_predictor | Workflow risk summaries; sales/operations predictive domain packs | Same repair. Collector previously dropped `status`, while training read it for labels; preserve it and exclude unresolved runs from labels. |
| retrieval_ranker | RAG learned source-reliability weight | Direct registry loading bypassed consent. This change checks current permission before reading artifact; fixed reliability weight remains fallback. |
| query_clusterer | Background learning produces persisted query clusters; live classification/bandit segments consume cluster metadata | Persisted cluster consumption is not proof that the deployed classifier artifact is used on each turn. |
| memory_promotion_scorer | Previously trained but no review consumer; now memory-promotion review API receives bounded advisory scores | Existing approval and auto-promotion thresholds stay authoritative. Scores do not approve, reorder or write memories. UI rendering of the new optional advice is not claimed. |
| retrieval_memory_learner | Existing composition over clustering, memory and ranking primitives | A composition, not another independent engine. No standalone deployed artifact was found; do not count component activity as independent model inference. |
| revenue_forecaster | Predictive domain packs, business signals and digital-twin paths | Real history/artifact/consent gates; no canonical deployed pointer in audit. |
| churn_risk_scorer | Per-account churn advisories → intelligence cards | One deployed pointer, not verified loaded/inferred; no consent recorded. Per-account features required; domain summaries must not score zero vectors. |
| cf_matrix_factorizer | Intelligence-card soft ranking | One deployed pointer, not verified loaded/inferred; no consent recorded. Item-affinity fallback remains. |
| sla_breach_predictor | Per-ticket prediction and support risk pack | Trainer still refuses missing ticket-level features and breached labels; counts do not activate it. |
| deal_loss_scorer | Per-deal prediction and sales risk pack | Trainer still refuses missing deal-level features and won/lost labels. |
| capacity_forecaster | Support/operations packs and digital twin | Requires measured volume history and deployed artifact/consent; no canonical deployed pointer in audit. |

The shared router already accepts backend-authorized `catalog_model_inputs`, but no production caller currently assembles this envelope. This work fixes a second gap: catalog results previously stopped outside the seven-slot fenced context. They now reach its bounded advisory evidence, shared by text and voice. It does **not** invent feature rows or run every model on every utterance. Dedicated existing consumers above remain the main path for real inputs. Advanced all-surface feature assembly remains incomplete.

## Implemented in this change

1. **Graph neural network**: actual CPU mean-neighbor graph convolution with a shared learned nonlinear node projection and directed pair classifier, using existing NumPy/scikit-learn dependencies. No GPU, PyG, new engine or duplicate registry. Training requires 100+ explicit binary labeled graph examples, chronological disjoint graph holdout, both classes, better-than-chance AUC and better log loss than prior baseline. Candidate edges must be withheld from message-passing context. Bounded node/edge/features, nonfinite rejection, numeric-only artifact loading, real save/load/predict.
2. **Meta-learning**: actual first-order Reptile initialization and few-shot adaptation across **organization-local** task episodes. At least 20 independent tasks; disjoint support/query/example IDs and held-out tasks; must improve query loss over support-only initialization and beat chance. No cross-tenant transfer, shared prior, federated permission, or external provider call. This is a deliberately narrower implementation of the former cross-organization scaffold; cross-organization meta-learning remains unavailable.
3. **Automatic lifecycle for graph, local meta-learning and existing self-supervised embeddings**: reuse the company-intelligence job, Redis coordination, current consent, cooldown, canonical registry and champion/challenger gates. No new scheduler or switch. A new draft target no longer triggers the 14-day retraining cooldown before its first actual training run. Discovery reads metadata only; missing advanced-data storage fails closed for that model without hiding the other training permissions. Existing Model Studio datasets and administrator-created `training` bindings provide data. No arbitrary document scraping. Self-supervised reconstruction variance still cannot auto-promote an embedding artifact: independent retrieval-quality validation is still required.
4. **Canonical dataset target fix**: model binding validation used nonexistent `ml_models`; actual ML registry is `trained_models`. Correct the shared validator and advanced collector. Every read remains scoped to authenticated organization. Existing binding purposes such as benchmark/reference do not qualify for training.
5. **Inference verification**: administrator-only `POST /api/admin/ml/models/{model_name}/verify-inference`, body `{"inputs": {"inputs": [<real model-specific rows>]}}` (intent accepts text strings; advanced structured models use their documented arguments). Calls the same org/consent/deployed-artifact boundary as internal intelligence. Bounded request, actual execution status, timestamp and registry reference; no training, promotion or provider generation. Response health applies to that request only; dashboards correctly remain `not_verified` without persistent evidence. No raw diagnostic inputs/outputs are persisted by this endpoint.
6. **Inference correctness**: authoritative caller organization passed to model wrappers; canonical catalog identity used when loading generic registry inference, preventing a classifier fallback from loading a specialized catalog artifact. Empty/fallback/nonfinite results cannot be labeled successful inference; NumPy scalars normalize for JSON. Ordinary runtime failures degrade without leaking provider exception text. This does not establish accuracy or business outcomes.

## Advanced inventory: what remains

All 12 entries remain in the existing catalog and administrator-only technical inventory; normal customer training controls do not expose them.

| Advanced entry | Implementation scope after this change | Dormancy / engineering still needed |
|---|---|---|
| active_learning | Existing real uncertainty sampling | Persisted sampling/review workflow over real inference streams is not integrated. |
| neuro_symbolic | Existing typed advisory constraint evaluator | Automatic vetted org rule/fact assembly is not integrated across surfaces. |
| causal_impact_analyzer | Existing paired observational estimator | Controlled identification, treatment assignment/confounder handling and causal validation remain unimplemented; no causal proof claim. |
| agentic_planning | Existing outcome-trained candidate ranker | Full authorized candidate/trajectory assembly and surface consumption remain incomplete. |
| world_model | Existing bounded numeric transition model | Full business simulation is not implemented; data/consent/artifact gates remain. |
| self_supervised_embeddings | Existing org-local LSA model, now automatic bound-corpus lifecycle | Independent held-out retrieval benchmark and compatible retrieval integration are missing; no substitution into global RAG vector space. |
| graph_neural_network | New real graph-convolution classifier + automatic lifecycle | Eligible provenance-bearing labeled datasets, consent and promotion needed; automatic graph feature assembly across surfaces remains incomplete. |
| meta_learning | New real tenant-local task meta-learning + automatic lifecycle | Eligible explicit task episodes, consent and promotion needed. Cross-tenant transfer is unsupported. |
| multimodal_router | Existing partial image selection through shared ModelRouter | End-to-end audio/video ingestion, provider execution and output verification still require engineering. |
| domain_specific_llm | Existing separate fine-tuning/agent-assignment machinery; catalog adapter still scaffolded | Department-specific approved corpus, held-out evaluation, catalog lifecycle and tenant-aware routing adapter still require engineering. |
| federated_learning | Disabled | Audited secure aggregation, validated differential privacy/accounting, deployed runtime, explicit legal/customer consent and ≥100 participants are not available. No plain aggregation was substituted or privacy asserted from boolean inputs. |
| diffusion_model | Provider/tool scaffold | Approved provider, paid generation tool, governed execution, content security and artifact handling still require engineering. No paid call or security bypass added to generic inference. |

**The 12 advanced categories are not all complete.** Bounded working algorithms and automatic lifecycle wiring are not full end-to-end activation. This change does not claim live readiness, ChatGPT/Claude parity, causal identification, or federated privacy.

## Data contract for new automatic trainers

Reuse existing `trained_models` entry (`base_model` equal to catalog name), `training_dataset_bindings` targeting that model ID (`purpose=training`, `target_type=model`), and existing `training_records`.

- Binding metadata: `schema_version: 1`, `model_name`, nonempty `target_definition`. Different target definitions cannot be mixed in one training run.
- Record metadata: `synthetic: false`, nonempty `source_ref`; graph/meta labels additionally require declared `label_source: human_reviewed`. These are provenance declarations, not independent proof of label truth or data quality. Training, holdout and promotion validate separately.
- Graph record `input`: JSON object with `node_features` (2–512 nodes × 1–32 finite features), `edges` (≤10,000 pairs of node indices), distinct `source`/`target`, `graph_id`, timezone-bearing `observed_at`; `expected_output` is literal `0` or `1`. Candidate edge cannot be present. Graph snapshots across temporal training/holdout must be disjoint.
- Meta record `input`: JSON object `task_id`, `support`, `query`. Each support/query example has unique `id`, `features` (1–32 finite values pre-normalized to [-10,10]), binary `label`. 2–100 examples per set, no example reused across tasks or sets. Holdout tasks are not used to update the initialization.
- Embedding record `input`: nonempty organization-local document text; ≥100 distinct texts and adequate vocabulary required. Artifact space stays `org_local_lsa`, incompatible with global RAG embeddings.
- Data discovery prompts existing medium consent dialog only for qualifying bound-data candidates. Closing grants nothing. Pause/revoke blocks future managed training/loads/inference. No organization consent or data binding is created by this change.

## Validation and review

- Initial affected regression set: **262 passed**; outbound provider calls blocked with opt-in offline pytest plugins and fake provider credentials.
- Broad backend service/ML/lint regression: **7,732 passed, 2 skipped** in 182.88 seconds. Final graph, consent, inventory and runtime regressions after the last edits: **41 passed**. Additional dataset/training regressions: **60 passed** before the final small metadata-discovery and offload refinements.
- The first broad run had three offline-harness failures; all three reproduced on unchanged main. A local-only harness now clears Google/Gemini credentials instead of making those providers appear configured and uses static localhost / numeric-address resolution without external DNS. HTTP transports, sockets and gRPC remain blocked. No production assertions were weakened. Final broad suite passes with those isolated test conditions.
- Additional tests exercise graph neighbor dependence, artifact roundtrip, leakage refusal, meta-learning held-out improvement, org-isolated bound records, RAG pause before registry access, real workflow feature assembly and measured labels, invalid inference rejection, shared evidence delivery, and advisory-only memory review.
- Two legacy predictive-interface regressions now target `capacity_forecaster`, retaining exact `not_available` assertions for missing methods. Workflow models have a dedicated real feature/inference adapter now; separate regressions verify it and its consent/data gates. This changes the exercised implementation path without weakening expected fallback behavior. Retrieval-ranker success fixture now explicitly grants mocked current consent; separate denial regression requires no registry access.
- No frontend claims, prices or toggles were added. New optional backend advice reports actual model output only, stays advisory and cannot grant approval. Consent/dialog behavior was explicitly requested earlier by the user.
- No dependency, schema, production flags or deployment changes. Supabase skill used: `skill://plugin_asdk_app_69d3e5ee6a708191baa733f7b8931995/supabase/SKILL.md`. Current Python select documentation checked; changelog Markdown fetch unsupported by search transport. Queries use the already installed Python client patterns; actual production schema checked read-only.
- Full CI, deployed SHA alignment, authenticated admin/non-admin UI, real organization inference, independent outcomes and the full combined text/voice standing quality batteries remain **NOT RUN for this branch**. In particular, shared evidence changes require those live quality batteries before release acceptance under engineering standards §8.
