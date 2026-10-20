# Model inference audit — 2026-10-20 UTC

Baseline: main `ee947c793`. Production SQL was read-only. This is an
inference-path audit checkpoint, not certification of the complete learning cycle.

## Production evidence

The `trained_models` / `model_versions` join returned 12 model records, with
two deployed version-2 artifact references: `catalog-churn-risk` and
`catalog-cf-matrix-factorizer`. Their version timestamps are July 19, 2026.
`model_predictions` has zero rows. Separate inference paths mean this is a
telemetry gap, not proof of zero inference.

`intelligence_outcome_events` contains 888 pending and 873 recorded events.
Recorded events are not independently verified business improvements. This audit
does not count them as eligible learning examples.

## Existing paths for the 14 catalog capabilities

All 14 have entries in `TRAINING_DISPATCH` in `backend/app/ml/intelligence_training.py`.
No new model family or parallel registry is needed.

| Catalog capability | Existing path inspected | Remaining runtime proof |
| --- | --- | --- |
| Intent classifier | `task_classifier.py` loads org catalog model | Artifact inference and routing correctness; no deployed registry version found |
| Query clusterer | `knowledge_intelligence_service.py` trains clusters inline and persists them | Validate scheduled population and downstream classification benefit; registry deployment alone is not the sole path |
| Memory promotion scorer | Training in company intelligence orchestrator; catalog factory | Live promotion consumer not established by this pass |
| Retrieval ranker | `learning_to_rank.get_weight_for_org` loads a deployed classifier and otherwise returns fixed weight | No deployed artifact found; validate quality against held-out retrieval outcomes |
| Retrieval memory learner | Catalog factory; wrapper delegates artifact load to its ranker | Non-catalog runtime caller not established by repository search |
| Workflow anomaly detector | Company intelligence trains and detects inline; shared inference also supports anomaly models | Draft registry rows do not disprove inline use; validate live scheduler/output |
| Workflow duration forecaster | Company intelligence trains and predicts inline; shared inference supports forecasters | Live scheduler/output and forecast accuracy |
| Workflow success predictor | Company intelligence trains and predicts inline; shared inference special-cases success predictor | Live risk predictions and later resolved outcomes |
| Revenue forecaster | Predictive operations loads catalog runtime | No deployed registry version; evaluate historical baseline and data sufficiency |
| Churn risk scorer | Churn advisory service loads org runtime and entity features | Registered v2 exists; loading, per-entity prediction and outcome labeling not live-tested |
| Collaborative filtering | CF rank service loads org runtime | Registered v2 exists; loading, recommendation ranking and later feedback not live-tested |
| SLA breach predictor | Predictive operations loads catalog runtime | No deployed registry version; real ticket features and labels |
| Deal loss scorer | Predictive operations loads catalog runtime | No deployed registry version; real deal features and resolved labels |
| Capacity forecaster | Predictive operations loads catalog runtime | No deployed registry version; daily history and held-out errors |

The shared `InferenceService` supports classifier, anomaly, forecaster and
fine-tuned LLM types, with a workflow-success special case. Its generic classifier
loader does not establish compatibility with every specialized catalog artifact;
embedding models are unsupported there. Preserve dedicated callers and test their
contracts before routing specialized artifacts through this service.

## First correction

`get_org_model_status` previously set `artifact_loaded=True` based solely on a
registry row with `deployed_version`. It now downloads the artifact and invokes
the catalog runtime's loader before reporting it loaded. Download and incompatible
artifact failures preserve the deployed version, report `artifact_load_failed`,
and retain the explicitly labeled fallback. This does not certify a prediction,
its accuracy, or business effectiveness. Dashboard requests now incur artifact
loading for deployed models; production latency must be checked before release.

Regression coverage: successful loading, failed download, failed deserialization,
and organization-scoped registry lookup. Together with existing registry/inference
tests: **6 passed** locally. Full CI and production acceptance: **NOT RUN**.

## Dependency sequence still to complete

1. Execute artifact-load and inference probes for each deployed model using its
   actual caller and authenticated organization. Record model/version, feature
   provenance, fallback reason and prediction ID. Do not create fake labels to
   cross training gates.
2. Confirm data gates and organization activation before training missing models.
   Preserve held-out evaluation and champion/challenger promotion safeguards.
3. Trace the seven capabilities through the existing router/facade: contextual,
   sentiment, causal, temporal, relational, predictive, adaptive. Current router
   inspection confirms contextual understanding, sentiment analysis, task routing,
   causal enrichment and outcome tracking integration points; it does not prove
   all seven participate in a live decision.
4. Implement the authenticated isolated scenario through existing execution and
   approval services, including independent connector readback. Assert tenant
   isolation, approval binding, retries/idempotency, source attribution and causal
   uncertainty. The inspected evaluation service alone is not this executor.
5. Observe a later independently measured outcome, verify eligibility and adaptive
   state changes, then demonstrate their effect on a subsequent decision. Synthetic
   outcomes must remain isolated from real customer learning and ROI metrics.

No production configuration, model promotion or database data was changed.
