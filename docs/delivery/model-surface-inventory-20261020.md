# Learning capabilities and model administration

Scope: implement the three approved visibility recommendations on baseline
`13f13c9bd`. This branch is separate from the seven-intelligence Phase 2 PR.

## Product behavior

- Learning uses the backend's `learningCapabilities`, not a four-model frontend
  array. The same panel serves the customer learning view and admin Engine tab.
  The customer disclosure loads the artifact-backed inventory only when opened.
  It reports capability purposes, data requirements, observed data, training
  validation status, the effective adaptive-learning setting, and outcome evidence.
- Models retains the existing custom-model registry and complete 14-entry
  operational built-in inventory. Profiles add artifact readiness, inference
  health, eligibility and verified outcome fields alongside the existing fallback.
- The 12 planned/disabled advanced entries are removed from member catalog
  responses. They are visible only in the admin-authorized technical inventory.
  Customer profiles cannot recover them through the member catalog.
- The obsolete frontend four-model list is removed. Supported controls derive
  from the existing backend dispatch and implementation availability. The SLA
  breach and deal-loss handlers explicitly return missing training columns, so
  they remain visible as existing capabilities without manual training controls.
- Admin training support is checked before Temporal queueing, as well as direct
  catalog training. Unknown, advanced and unsupported requests cannot queue jobs.
  Existing trainer eligibility, held-out evaluation and promotion gates remain.
- The existing admin dependency still enforces server-confirmed membership roles.
  Buttons require a fresh admin result; hiding a button is not the security boundary.

## Evidence semantics

| Field | Meaning |
| --- | --- |
| Catalog TRAINED | Existing capability implementation metadata; never used as a UI runtime fallback. |
| Artifact loaded | The organization artifact downloaded and deserialized through the existing Phase 1 check. |
| Inference health | Not verified by artifact loading. No successful-inference certification is invented. |
| Observed data | Existing org-scoped counters; not proof of eligible labels or held-out validation. |
| Data eligibility | Requires training validation for supported handlers; unavailable for unsupported handlers. |
| Adaptive learning enabled | The existing global/org adaptive setting; does not imply all learning is active or disabled. |
| Verified outcomes | `null` / not verified until independently established per model. Ledger scores or recorded events are not relabelled verified improvement. |

These changes do not create missing inference/outcome evidence. They expose the
absence honestly, including when artifacts exist. The earlier exact-copy tests
for “Ready to use” and “Actively predicting” were intentionally strengthened to
require artifact/deployment wording and explicit separation from inference proof.
Heuristic fallback is no longer labelled active learning. Unknown status is not
classified as a planned model. No labels, outcomes or metrics are fabricated.

## Validation

- Full web regression: **1,880 passed**, 294 files, zero failures.
- Changed UI ESLint: no errors; shared `lib/api.ts` retains four pre-existing
  unused-import warnings. TypeScript passed.
- Production Next.js build passed using the same non-secret placeholder values
  as CI. Final status-classification changes were then checked with the focused
  rendering/status tests and TypeScript.
- Final backend regression batch: **95 passed**, including existing catalog,
  artifact honesty, admin overview permissions, training support and learning
  regressions. The inventory suite includes the actual role dependency: non-admin
  technical catalog and training both return 403. Earlier focused counts overlap.
- UI rendering tests cover ordinary members, admins, supported vs unsupported
  training, admin-only advanced inventory and unknown/zero outcome distinctions.
- Backend provider sockets/DNS blocked via `tests.offline_network_guard`.

No migrations, production flags, model training, artifact promotions or provider
calls were performed. CI and authenticated deployed UI/API acceptance are release
checks, not claimed from local tests. This change does not certify the advanced
scaffolds, inference quality or the end-to-end learning cycle.
