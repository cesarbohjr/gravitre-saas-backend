# Supabase migration history drift — diagnosis only

**Date:** 2026-08-11  
**Project:** `smyeexlrqdpymwjmgzqu`  
**Method:** `supabase migration list --linked` + read-only `supabase db query --linked` against `supabase_migrations.schema_migrations` + schema/data probes via service role  
**Constraint honored:** No `migration repair`, no history rewrite, no force-push, no delete/reorder of migration records.

Supporting artifacts:
- `docs/delivery/_migration_list_linked.txt` — full list output  
- `docs/delivery/supabase-migration-history-drift-mapping.json` — remote-only → local file map  
- `docs/delivery/_migration_drift_schema_probes.json` — live schema probes  

---

## Executive picture

| Layer | What exists |
| -- | -- |
| **History drift** | **YES — CONFIRMED.** 11 remote versions not in local files; 19 unique local versions not in remote history. |
| **Order/checksum drift among shared versions** | **Not observed.** 174 versions present on both sides with matching version IDs in the list. CLI list does not surface per-file checksums; no evidence of reordered shared versions. |
| **Live schema/data vs intended local migrations** | **Mostly aligned in practice** (probes below). Drift is primarily **history bookkeeping**, not a blank remote. Some local-only files were applied under **different version timestamps** (Dashboard), or via **service-role / out-of-band SQL** without a matching history row. |

**Bottom line:** The blocker for `supabase db push` (“Remote migration versions not found in local migrations directory”) is **real history drift**. It is **not** evidence that production is missing those 11 migrations’ SQL — remote rows name the same migrations as local files, stamped with wall-clock versions when applied under `created_by=cesar.bohorquez.jr@gmail.com`.

---

## Phase 1 — Exact drift state

### Counts (from `migration list --linked`, 2026-08-11)

| Set | Count |
| -- | -- |
| Present on **both** local and remote | **174** |
| **Remote-only** (history row, no local file with that version) | **11** |
| **Local-only** (file version, no remote history row) | **20 list rows / 19 unique versions** (version `20260725120000` has **two** local files) |
| Remote `schema_migrations` total rows | **185** (= 174 + 11) |
| Local `supabase/migrations/*.sql` files | **194** |

### 1A. Remote-only versions (complete)

| Remote version | Remote `name` | `created_by` | Matching local file (different version) |
| -- | -- | -- | -- |
| `20260725085714` | `agent_avatar_url` | cesar.bohorquez.jr@gmail.com | `20260725120000_agent_avatar_url.sql` |
| `20260725234024` | `agents_icon_avatar_color_columns` | cesar… | `20260725190000_agents_icon_avatar_color.sql` |
| `20260731001645` | `add_google_ads_connector_type` | cesar… | `20260730120000_add_google_ads_connector_type.sql` |
| `20260801060750` | `workflow_schedules_once_timezone` | cesar… | `20260801120000_workflow_schedules_once_timezone.sql` |
| `20260802223452` | `workflow_runs_partial_success_status` | cesar… | `20260802120000_workflow_runs_partial_success_status.sql` |
| `20260804021749` | `chat_artifacts_storage` | cesar… | `20260804020000_chat_artifacts_storage.sql` |
| `20260808065607` | `department_resource_assignments` | cesar… | `20260808010000_department_resource_assignments.sql` |
| `20260808085000` | `voice_agent_profile_and_minutes` | cesar… | `20260808120000_voice_agent_profile_and_minutes.sql` |
| `20260808204958` | `voice_plan_included_and_topups` | cesar… | `20260808140000_voice_plan_included_and_topups.sql` |
| `20260809044816` | `archive_scaffolding_meson_addons` | cesar… | `20260809010000_archive_scaffolding_meson_addons.sql` |
| `20260809085843` | `billing_plans_voice_included_list_prices` | cesar… | `20260809120000_billing_plans_voice_included_list_prices.sql` |

**Origin (traced, not guessed):**
- These are **not** unexplained orphans. Remote `name` matches local migration stems 1:1.
- Statements sampled from remote for `agent_avatar_url` / `agents_icon_avatar_color_columns` match the intent of the local SQL files.
- `created_by` is Cesar’s email on all 11 → applied through **Supabase-linked apply path that stamps wall-clock version IDs** (Dashboard / CLI apply under live clock), **not** recorded under the repo’s rounded `…120000` filenames.
- Prior program evidence of the same class: commit `de2d222d` (*“apply google_ads type CHECK after migration version collision… Applied add_google_ads_connector_type in Supabase and renumbered the repo migration”*). Remote now holds `20260731001645` / `add_google_ads_connector_type` while repo file is `20260730120000_…`.

### 1B. Local-only versions (complete unique list)

| Local version | File(s) | Remote twin? | Notes |
| -- | -- | -- | -- |
| `20260725120000` | `…_agent_avatar_url.sql` **and** `…_org_creator_owner_role.sql` | Avatar → remote `20260725085714`. **org_creator:** no remote name match found | **Duplicate local version ID** (two files, one stamp) |
| `20260725180000` | `seed_production_env_and_owner.sql` | No remote name match | production env rows exist (probe: 3) — apply path **UNCERTAIN** |
| `20260725190000` | `agents_icon_avatar_color.sql` | → remote `20260725234024` | History under different version |
| `20260726120000` | `platform_admin_cesar_gravitre_app.sql` | No row for this version; older `platform_admin_cesar` @ `20260609190000` exists | `cesar@gravitre.app` platform_admins row `@ 2026-07-26` — data present, history for **this** file version absent |
| `20260730120000` | `add_google_ads_connector_type.sql` | → remote `20260731001645` | Documented collision renumber |
| `20260801120000` | `workflow_schedules_once_timezone.sql` | → remote `20260801060750` | |
| `20260802120000` | `workflow_runs_partial_success_status.sql` | → remote `20260802223452` | Live probe: `partial_success` queryable |
| `20260804020000` | `chat_artifacts_storage.sql` | → remote `20260804021749` | |
| `20260805140000` | `users_job_title_department.sql` | **No remote history name** | Live columns `users.job_title`, `department` **present** — apply path **UNCERTAIN** (out-of-band likely) |
| `20260805210000` | `enable_rls_intelligence_public_tables.sql` | **No remote history name** | Effects not fully proven this pass; related older RLS migration `enable_rls_flagged_public_tables` @ `20260617120000` exists |
| `20260805220000` | `audit_events_org_action_created_idx.sql` | **No remote history name** | Index presence **NOT PROBED** this pass → **UNCERTAIN** |
| `20260805221000` | `perf_advisor_fk_indexes.sql` | **No remote history name** | Index presence **NOT PROBED** → **UNCERTAIN** |
| `20260807140000` | `workflow_runs_flagged_for_review_status.sql` | **No remote history name** | Live probe: `status=flagged_for_review` queryable |
| `20260808010000` | `department_resource_assignments.sql` | → remote `20260808065607` | Table exists |
| `20260808120000` | `voice_agent_profile_and_minutes.sql` | → remote `20260808085000` | `voice_minutes_per_month` on plans |
| `20260808140000` | `voice_plan_included_and_topups.sql` | → remote `20260808204958` | |
| `20260809010000` | `archive_scaffolding_meson_addons.sql` | → remote `20260809044816` | |
| `20260809120000` | `billing_plans_voice_included_list_prices.sql` | → remote `20260809085843` | Live prices 59/149/349 |
| `20260811120000` | `restore_billing_plans_research_lookups.sql` | **Absent from remote history** | **CONFIRMED** service-role apply 2026-08-11 (`billing-plans-research-lookups-restore-2026-08-11.json`); live research keys present; history never updated |

### 1C. History vs live STATE

| Question | Answer |
| -- | -- |
| Is the problem only history? | **Primarily yes** for the 11 remote-only / renamed pair. |
| Would a fresh apply of all local files reproduce live? | **Not guaranteed identical.** (1) `20260729120000` on remote wiped research keys (known); restore was service-role not history. (2) Duplicate `20260725120000` is ambiguous. (3) Several Aug 5–7 files have schema effects without history rows — re-running them may be idempotent (`IF NOT EXISTS`) or may conflict. |
| Is production “missing” the 11 remote-named migrations? | **No.** Those SQL changes are recorded as applied under wall-clock versions. |

---

## Phase 2 — Repair options (no action taken)

### Option A — Reconcile history table only (`migration repair`)

Mark versions applied/reverted so CLI stops complaining.

| | |
| -- | -- |
| **Risk** | **MEDIUM–HIGH** if used to “revert” the 11 remote wall-clock rows (would claim real applies never happened) or to mark local versions applied **without** confirming schema. |
| **When it helps** | For local-only versions whose SQL is already live and **never** recorded (e.g. `20260811120000`, possibly Aug 5–7). |
| **When it hurts** | Using `reverted` on remote-only twins of real local files. |

### Option B — Forward-only new migration(s); do not edit old history rows

Add idempotent SQL for any true schema gaps; leave existing history rows untouched.

| | |
| -- | -- |
| **Risk** | **LOW** for schema safety. |
| **Limitation** | **Does not alone unblock** `db push` while remote versions remain absent from the local directory — CLI still errors on remote-only IDs. |

### Option C — Rewrite / delete / reorder already-recorded history

| | |
| -- | -- |
| **Risk** | **HIGH** |
| **What goes wrong** | False “not applied” → double-apply destructive SQL; false “applied” → skipped real migrations; loss of audit trail of what Cesar’s Dashboard applies actually ran; multi-env irrevocable confusion. |
| **Recommendation** | **Do not use** unless no other path exists (not the case here). |

### Option D (recommended) — Align local filenames to remote version IDs, then handle true orphans

1. **Rename (git mv) the 11 local files** to the remote wall-clock `version` stamps (keep names/content). No `schema_migrations` mutation. Makes “remote versions not in local” false.  
2. **Resolve duplicate** `20260725120000` (`org_creator_owner_role`) with a unique unused version after verifying whether its SQL is already live.  
3. For remaining local-only without remote twin (`20260811120000`, Aug 5–7 cluster, seed/platform_admin):  
   - If schema already matches → **Option A** `repair --status applied` for that version only (history bookkeeping).  
   - If schema gap remains → **Option B** forward idempotent migration / careful push of that file only.  
4. Never `repair --status reverted` the 11 remote wall-clock rows.

| | |
| -- | -- |
| **Risk** | **LOWEST among options that actually clear the push blocker.** Renames are repo-side; remote history stays the honest record of Dashboard applies. Residual risk is mis-handling the non-paired local-only set — mitigate with per-file schema checks before `repair applied`. |

---

## Recommendation

**Prefer Option D** (align local file versions to remote history), then selective Option A/B only for true orphans (`20260811120000` and any Aug 5–7 file proven already applied or still missing).

**Do not** use Option C.  
**Do not** `repair reverted` the 11 remote-only rows — they are the real apply record.

### Explicit hold

**No repair in this pass.** Await Cesar’s named choice among A / B / D (or a hybrid of D+A) before any history or rename work proceeds.

---

## Uncertainties (stated plainly)

1. Exact Dashboard vs CLI mechanism that chose wall-clock stamps — known `created_by` and name match; mechanism inferred as live apply clock, not a second SQL dialect.  
2. Whether `20260725180000_seed_production_env_and_owner` and `20260725120000_org_creator_owner_role` SQL ran in full — related data exists; dedicated history rows for those local versions do **not**.  
3. Whether Aug 5–7 index/RLS files were applied verbatim or only partially — some effects present; index-level proof incomplete for `20260805220000` / `20260805221000`.  
4. Fresh-DB replay of entire local chain vs current prod — **not run** (would require disposable DB); diagnosis does not claim bit-identical replay.
