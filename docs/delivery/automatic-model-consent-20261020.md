# Automatic model lifecycle and training consent — implementation checkpoint

This change is an implementation checkpoint, not completion or production acceptance of all 26 models. It builds on the model-surface inventory change in PR #521. No models have been trained against production data, no consent has been granted on a customer's behalf, and no production deployment or migration was performed.

## Approval experience

The shared Intelligence shell includes an administrator-only, medium-sized accessible dialog when the backend detects candidate training data. The dialog explains what model, why, data requirements, when training could start, processing location limitations, organization-only security scope, and how to pause, resume, revoke, or open existing security settings. The customer-visible dialog and controls were explicitly requested by the user on 2026-10-20; they are not invented product claims.

Copy starts: “Gravitre has detected data for training the [model] model. Training will begin after your approval, if data validation passes.” Detection and approval are explicitly not proof of eligible labels, promotion, or improved results.

Opening, dismissing, or pressing Escape grants nothing. “Not now” stores deferral. Approval is bound to the exact server-generated disclosure digest. Changed disclosures require renewed approval. Members cannot read or mutate the technical approval API. The server records the authenticated administrator, timestamp, scope, and recent permission history in existing organization settings, with compare-and-swap protection against overwriting concurrent settings changes. A failed permission read denies training. No cross-tenant consent can be granted through this API.

The dialog includes persistent Training permissions review controls on Intelligence pages. Pausing/revoking blocks new shared-loader and unified-service inference even for cached models, and blocks new artifact registration. In-flight work may finish; artifacts and historical outputs are not deleted by revocation. Existing security settings remain the source for access, retention, and residency controls; the dialog does not claim or change a physical processing region.

## Existing learning jobs and model inventory

Existing company-intelligence jobs remain the background entry point for both Temporal and in-process scheduling. Existing intent, workflow, ranker, clustering, and memory trainers are not duplicated. They now check reviewed consent before their scheduled training steps. The complementary reconciliation handles revenue, churn, collaborative filtering, capacity, bounded planning, and bounded world transitions. Redis coordinates this work across workers; missing coordination means dormant, not an unsafe local fallback. Recently registered versions observe a 14-day cooldown. Each trainer still validates its own data; the existing held-out champion/challenger registry gate still decides promotion.

The existing readiness service's registry-name/type mismatch and ML upgrade service's `models` versus `by_model` mismatch were repaired. The generic inference service now selects the actual catalog class for catalog artifacts, checks tenant ownership, checks current permission before cache access, and refuses non-deployed versions for automatically managed catalog entries. Legacy registry base aliases cannot bypass permission checks.

Static TRAINED remains implementation metadata. Artifact readiness, successful inference, consent, data eligibility, and independently verified outcomes remain separate evidence. Advanced models remain outside ordinary customer model/training inventories; the explicitly requested approval experience is for administrators.

## Advanced implementation status

| Entry | Implemented in this checkpoint | Remaining work |
| --- | --- | --- |
| Active learning | Normalized-entropy sampling of valid inference distributions, bounded input and deterministic ranking | Persist sampling/review integration with real inference streams and verified labels |
| Causal impact | Real measured before/after pairs, observational effect and sampling interval, no fabricated causal confidence or accuracy | Controlled causal identification and validation; observational estimates are not causal proof |
| Neuro-symbolic | Typed symbolic constraint evaluation for the existing neural pipeline; advisory only | Bind vetted organization rules/facts to all applicable live surfaces |
| Agentic planning | Reloadable outcome-trained logistic scorer, temporal holdout, automatic org-local measured-revenue adapter | Wider trajectory domains, current candidate assembly, end-to-end live use |
| World model | Reloadable bounded Ridge transition predictor, baseline comparison, observed-support refusal, automatic 500-row / 180-day measured-revenue gate | Broader validated transitions and end-to-end live scenario assembly; not a full business simulator |
| Self-supervised embeddings | Real reloadable TF-IDF/SVD org-local embeddings, normalized output, separate vector space | Approved corpus ingestion and independent retrieval-quality evaluation; reconstruction variance cannot promote it |
| Graph neural network | Existing scaffold retained honestly | Neural graph training, graph labels/features, compatible compute and inference integration |
| Meta learning | Existing scaffold retained honestly | Privacy-governed task transfer and evaluation |
| Multimodal | Existing partial routing retained | Complete provider-backed modality inference and policy integration |
| Domain-specific LLM | Existing fine-tuning infrastructure retained | Eligible corpus adapter, provider-purpose consent, evaluation and department routing |
| Federated learning | Existing disabled implementation retained | Deployed consent lifecycle, audited secure aggregation, validated differential privacy, participant quorum and governance prerequisites |
| Diffusion | Existing scaffold retained honestly | Provider/tool integration, security/cost controls and output handling |

The existing SLA/deal trainers still lack valid source feature/label ingestion. They remain unavailable for training; this change does not invent missing columns or labels.

The shared IntelligenceRouter accepts up to four explicitly assembled, org-authorized catalog inputs through its existing enrichment method; chat already delegates to that router. This is a shared extension point, not proof that every model is assembled into every text/voice surface today. Complete cross-surface input assembly, prompt consumption, real microphone verification, and independently measured improvement remain outstanding. No new intelligence engine was introduced.

## Validation

- Full web suite: 1,886 passed in 295 files; final dialog/capability tests: 9 passed.
- Backend regression set: 213 passed across ML, learning layer, extended intelligence, company learning/scheduler, catalog routes, and ReAct inference parity. Additional final focused checks cover alias and permission regressions.
- TypeScript passed. Changed TSX ESLint passed.
- Production Next build passed with nonsecret CI placeholders. First attempt encountered an unreadable local Turbopack persistence cache; preserving that cache outside the build directory and rebuilding resolved it.
- Causal real-column regression was strengthened to require an actual before/after pair. Existing artifact/churn tests now state an explicitly approved training-scope fixture so they continue testing storage and promotion; separate new tests prove refusal without consent, revocation, scope changes, tenant binding, and real member-role enforcement. No prior artifact/promotion assertions were weakened.
- No authenticated production UI, deployed SHA, production inference latency, live training, or independently verified customer outcome proof: **NOT RUN — draft implementation, not deployed**.

## Release status

Not ready to claim all 26 models fully operational. Keep this change in draft while completing the remaining implementations, real shared-surface integration, CI, and live acceptance.
