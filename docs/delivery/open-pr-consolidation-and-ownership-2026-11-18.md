# Open PR reconciliation — one execution program, no duplicate ownership

**Inventory:** 2026-11-18 UTC. GitHub open PR list, **11 PRs**: #580, #588, #596, #600, #603, #604, #610, #611, #612, #615, #616.
**Governing scope:** `master-qa-remediation-program.md` and all **43 IDs** in `master-qa-remediation-register.v2.json` (30 P0, 13 P1). The seven-stage R0–R6 dependency sequence is unchanged.
**Hard hold:** **Do not merge or deploy ANY PR until every required one of the 12 QA gates passes on the agreed exact head(s), followed by explicit owner authorization.** No production writes, feature activation, destructive retirement, migration or release is implied by this reconciliation.
**Certification:** Do not turn source overlap, a prior run, or an implementation commit into a finding PASS. All 43 findings remain uncertified in the current ledger; ECO-001 is administratively consolidated into ECO-002, not remedied.

## Canonical ownership and decisions

| PR | Open branch scope / actual file comparison | Decision: single owner; completed vs unresolved |
| --- | --- | --- |
| **#611** (main remediation) | 354 files changed at inspected head `53bb702` *before* this reconciliation; active canonical execution, approval/outbox/recovery, QA/test and audit register. | **Canonical integration/evidence owner**, R0–R6 and all 43 register IDs. Continue actual repairs and exact-head QA. PR remains open; no release. |
| **#612** (QA00/QA10 isolated) | **4/4 touched paths overlap #611.** The workflow recovery lease SQL and source governance test were **byte-identical** at review. The proxy implementation and its audit test differed only in incremental proxy handling/coverage. | **Subsumed into #611 without merging #612**: ported the missing bodyless 204/205/304 handling and additional 401 tests to #611 (`94535df9`, `374eebec`). Verify same behavior on exact-head CI. Freeze #612 implementation; keep open for traceability unless owner separately authorizes closing. Do **not** reapply its migration. |
| **#615** (ECO-002 stacked, 52 commits / 20 paths) | 4 paths overlap #611 including `intelligence_router.py`, `ci.yml`, joined Chat/Agent PG tests. New `router_stage_timing.py`, correlated reports, dependency probes, 3 workflows. **#611 already instruments `intelligence_router.py` using `routing_stage_metrics`.** GitHub reports stacked PR **dirty/conflicting** against its moving parent. | **No second routing timing authority.** #611 is canonical integration owner; #615 retains **unique measured baseline, correlation/dependency DAG, real-ingress proof and perf methodology** pending compare against existing `routing_stage_metrics` and reports. Migrate only demonstrably nonduplicated tests/evidence into the master QA gate after measured parity; retire duplicate timing wrapper rather than running both. No rebasing/merging as a shortcut. |
| **#616** (ECO-003 stacked, 13 commits / 6 paths) | 1 shared path `context_assembler.py`; unique profiler, context report/tests and targeted workflow. **#611 already measures context stage latency through `context_stage_metrics`** and safe exception log. The alternate branch adds `perf_counter` measurements and request-stage logging. | **One context instrumentation implementation.** #611 owns stage metrics. #616 supplies **nonduplicated report, tenant-negative tests and representative nonproduction evidence** after comparison. No independent timing layer, caching, or parallelism until baseline and cross-tenant safety verified. |
| **#610** (Voice 3.0, V0–V7) | 14 paths; only shared `backend/app/config.py` and `test_source_governance.py` with #611; governance test byte-identical. Unique Pipecat transcript/turn/audio implementations and their tests. | **Sole Voice-specific implementation owner** for STT, turn finality, PCM, audio and V0–V7. #611 owns shared action/governance parity and QA30 evidence import. Do not duplicate acoustic/turn logic in #611. Real iOS/device/human evidence pending. |
| **#600** (conversation + PCM repairs) | 21 paths, **2 overlap #611**: `unified_turn_reasoning_service.py` and a CI workflow; also touches `agent_intelligence.py` in common with #580. Independent browser PCM diagnostics, provider auth backoff, dialogue and connector-discovery changes. GitHub reports conflicts. | **Split ownership by component, not a parallel chat/voice authority:** #610 evaluates/owns audio+PCM client changes; #611 evaluates/owns shared dialogue, provider routing/auth backoff, contextual connector discovery and tests. Compare before porting, preserve coherent behavior and avoid duplicate fallback/clarification state. No blanket cherry-pick. |
| **#604** (Nango/OAuth catalog coverage) | 34 changed paths and **zero exact file overlaps with #611** at review; 12 dashboard OAuth integrations reported in dev, provider app credentials/scopes and live consent still pending. | **Keep connector catalog/authorization as distinct implementation work**, but #611 remains the execution governance and connector availability owner. Import connector capabilities into existing governed tool registry only after token/scope/revocation negative tests. Nango provisioning alone is not working customer OAuth. |
| **#596** (Agency Agents) | 6 paths, **zero exact #611 overlaps**; seed/report/test + delivery spec, not complete 283-profile execution certification. | **Distinct deferred feature track**, mapped into #611 Agent/Play/Marketplace acceptance when dependency gates permit. No separate dispatcher, premature catalog claims or production marketplace publishing. |
| **#588** (source scheduler + Slack) | 5 paths, **zero exact #611 overlaps**; operational fixes/tests, full CI and Slack consent/readback outstanding; mergeability dirty. | **Keep bounded operational correction**, reconcile against #611 R4/R6 and existing connector auth. Do not claim Slack OAuth reconnect complete. Port changes only if needed by canonical code; don't duplicate backoff caches or schedulers. |
| **#580** (seven-intelligence evidence) | 15 paths, 1 exact #611 overlap `routers/plays.py`; additionally `agent_intelligence.py` overlaps #600. 168 offline evidence probes reported; live gates pending. | **Retain test evidence as distinct QA05 input** while #611 owns actual multi-surface intelligence consumption and Play execution. Compare `plays.py` changes before porting; prohibit duplicate intelligence or review owners. |
| **#603** (marketing About/Careers art) | 5 paths, **zero exact #611 overlaps**; asset/page updates only. | **Independent cosmetic work**, not a remediation gate and not a reason to activate separate CI master or deploy. Keep open pending agreed final release sequencing. |

## Shared-path collision summary

- **#612 ↔ #611: four paths** — reconciliation above makes #611 canonical; two previously byte-identical, two incremental proxy fixes/tests ported.
- **#615 ↔ #611: four paths** — router instrumentation, CI, Chat PG and Agent PG tests; mergeability conflict means **manual behavioral comparison first**.
- **#616 ↔ #611: one path** — same context assembler, competing stopwatch implementation.
- **#610 ↔ #611: two paths** — shared settings and byte-identical governance test; Voice ownership remains #610.
- **#600 ↔ #611: two paths** — shared reasoning and CI; **#600 ↔ #580: one path** — agent intelligence.
- **#580 ↔ #611: one path** — Play router.
- **#604/#596/#588/#603: no exact file overlap with #611** on inspected heads; semantic dependency, especially connector/readiness, still requires regression review.

File overlap is not proof of behavior equivalence; lack of overlap is not proof of architectural independence.

## Nonduplication operating rules

1. **R0–R6 remains sequential** at the finding-closure level; concurrent implementation is allowed only in nonconflicting areas. Don't spin up new PRs or parallel routing/execution owners.
2. Every change must identify one canonical runtime owner, one responsible PR, related ECO/DEC/P27 IDs, and regression/QA lane. Do not replace already-owned `routing_stage_metrics` or `context_stage_metrics` with duplicate wrappers.
3. Where branches differ, **inventory unique behavior → assess parity/conflicts → port minimal missing code/tests to owning PR → run exact-head tests → mark originating branch as subsumed in this ledger**. This does not imply GitHub merge or close.
4. **#610 only:** Voice STT, natural duplex, turn arbitration, PCM. **#611 only:** shared governed tool execution, approvals, context/intelligence, Agent/Play/Canvas end-to-end outcomes. Other PRs are source branches/feature queues until a nonconflicting integration is verified.
5. All 12 required QA gates (including missing/blocked lanes, no skipped-as-pass) must pass before any final merge/deploy. Deployed-provider and physical-device proof remain separate and require explicit authorization. Keep owner decision controls and production flags OFF.

## Next concrete reconciliation gates (no merge/deploy)

1. **#612**: run new proxy response/tenant tests on #611 exact head; compare the four final files and mark fully source-subsumed only if no behavior gap remains.
2. **#615/#616**: diff timing method names, emitted stage labels and data format against #611's existing `routing_stage_metrics` and `context_stage_metrics`; map unique report/real ingress/dependency tests into the canonical measurement, without running parallel emitters. Record representative p50/p95 on privacy-safe nonproduction traces.
3. **#600/#580**: perform careful shared `agent_intelligence`, `unified_turn_reasoning_service`, `routers/plays` and provider auth backoff comparison; import only verified missing behavior into the corresponding #610/#611 code owner.
4. **#604/#588/#596**: connector credentials/readiness and Marketplace feature acceptance remain separate. Map to existing tool/Play contracts; no duplicate agents, registry or scheduled loop.
5. Resume open ECO-002 and the 43-finding register in dependency order, repair confirmed QA failures, and record exact-head evidence. **No merge, deployment, paid live QA or production mutations** during consolidation.

**Evidence sources:** GitHub open PR inventory / file lists / branch blob comparisons performed 2026-11-18; master v2 register, master QA program and QA00–90 release manifest on #611. GitHub PR descriptions or old CI results do not establish full certification.
