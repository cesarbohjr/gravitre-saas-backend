# PR queue consolidation decision — 2026-11-17

Administrative consolidation only, owner-directed. **Closing a pull request does not mean the unique code has been integrated, tested, certified, merged, deployed, or discarded. Do not delete source branches.**

## Active PR cap: three

| PR | Owner | Rule |
|---|---|---|
| #611 `feat/master-qa-tranche27-orchestration` | 43-finding register, canonical platform integration and all 12 QA gates | All non-Voice, non-OAuth independent work must be tracked and selectively reconciled here |
| #610 `feat/qa-master-voice-parity-gates` | Voice 3.0 V0–V7, STT/turn/PCM | Voice-owned source, never silently reimplemented in #611 |
| #604 `codex/catalog-nango-connector-coverage` | Distinct provider OAuth / Nango catalog coverage | Remains separate until its connector-specific acceptance; #611 owns cross-surface runtime integration |

## Closed without merging — work preservation ledger

| PR | Archived head SHA | Unique work not to lose and disposition | Engineering truth |
|---|---|---|---|
| #612 | `65ebd79074facffe7992fc2148971084e594e068` | QA00/QA10 proxy and recovery SQL; all 4 changed paths already on #611, 3 identical and 1 comment-only deviation | **Functionally covered by #611**, do not replay |
| #615 | `16d90b71344fdc02a3601308562ab403221f91de` | ECO-002 correlated latency, per-request shape/report scripts, dependency DAG/probes and joining tests | **Unintegrated unique work remains**. Selectively carry nonduplicative reporter and tests onto canonical `routing_stage_metrics.py`; do not copy `router_stage_timing.py` or overwrite #611 router and CI; measured p50/p95 pending |
| #616 | `a7eec01996f960a1f74dfa510d5dee4813d48d0e` | ECO-003 correlated full-assembly latency report and tenant dependency contracts | **Unintegrated unique work remains**. Reconcile into `context_stage_metrics.py` stage taxonomy, keeping one timing implementation; add privacy-safe total measurement and negative tests after comparison |
| #600 | `b57aad0d1192123300b8c03b57777034aa42cf7a` | Provider auth backoff and scenarios, connector discovery, clarification repair, PCM/client diagnostics | Auth backoff identical in #611; dialogue/discovery on #611 with additional fixes; any unique client audio belongs #610, and remaining test claims must be checked before closure evidence |
| #580 | `9b1b897d278b6cd4a7d2263fdf57beb38f1f9e74` | Independent-review confidence honesty, evidence matrix, seven-capability differential and read-only live preflight | Consensus provenance guard and targeted test ported to #611 (commits `e0cdb132`, `ce761969`), remaining unique scripts/QA05 evidence **not yet integrated**; no live certification |
| #596 | `4505e97797ac5433a7e92e01dd7584cee462e773` | Agency marketplace 283-role inventory/reconciliation and release reporting | **Unintegrated unique work remains**; track as Agency marketplace product work under #611's canonical agent/Play/connector execution acceptance, not as a certified delivery |
| #588 | `e0e75955d0faa26994ebf5039adc35f9f360a43f` | Slack OAuth revoked-token retry and source-scheduler ownership/audit attribution fixes + tests | **Unintegrated unique work remains**. Review against live #611/source scheduler and copy only confirmed missing repairs and regression tests |
| #603 | `e254f9ec932e7eed09c0f74cf9e96921f025cfb7` | About/Careers marketing illustrations and responsive art-card design | **Unintegrated unique marketing UI work remains**, not a 43-finding closure. Retrieve from the source branch only when marketing release scope is authorized |

## Nonduplication integration checklist (PR #611)

1. Review unique PR #615 report/probe/test code against existing ECO-002 timing; add missing correlated baseline and regressions to **one** canonical routing implementation. Measured runtime p50/p95 and source-to-caller proof required.
2. Review #616 context assembly total-span and tenant-negative tests; reuse `context_stage_metrics.py`, preserving exception/cancellation semantics. Existing collector-failure fix: `646d37b`, tests `0421620`.
3. Review #580 per-cell intelligence evidence, play/agent data propagation and council confidence; reuse `confidence_honesty.py` and the current execution authority. Current council guard `e0cdb132`, test `ce761969`.
4. Review #600 any remaining unique provider/dialogue tests and voice diagnostics; no duplicate provider auth backoff; voice implementation under #610.
5. Review #588/source scheduler, #596 marketplace and #603 UI only in their appropriate ordered phase. #604 remains active provider-catalog owner.
6. Validate every transferred change against required positive and negative tests, exact SHA, cross-surface effect and register entry; neither closing a PR nor code presence counts as a certified finding.

**Restrictions:** none of these branches has been merged. No source branches are to be deleted. No deployment, production mutation, flag enablement, provider writes or release certification is authorized. All 12 QA gates and completion of the 43-finding master remediation program remain mandatory before owner-authorized final merge/deploy.
