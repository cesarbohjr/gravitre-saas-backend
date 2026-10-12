# Memory lineage: proposed handling of legacy untagged memories

Status: **proposal for the owner's review. Nothing here has been run, and nothing retires or accepts rows automatically.**
Date: 2026-10-12. Related: PR #374, migration `20261012070000_agent_memory_source_lineage.sql` (not applied).

## Why there is a legacy set

`purge_connector_memories` removes agent memories and customer observations by the connector they name (`source_connector_id`). Rows written before `MEMORY_SOURCE_LINEAGE_ENABLED` is turned on name no connector, so a disconnect cannot remove them. They are not tagged after the fact: their text cannot tell us which connection they came from, and a wrong tag would delete the wrong customer's data or keep the right one.

## How to size it

Run `docs/delivery/memory-lineage-legacy-audit-2026-10-12.sql` (read-only; safe inside `BEGIN READ ONLY ... ROLLBACK`). Query 2 puts every agent memory into exactly one group. Query 3 breaks the two groups that may hold connector content down by org. Query 5 sizes untagged customer observations by source system. Record the counts in the release report before deciding.

`tests/db/test_memory_lineage_legacy_audit_pg.py` runs the file against real PostgreSQL in a read-only transaction and checks the grouping.

## Groups and proposed handling

Each group gets an owner decision: **retire** (the row stops being recalled), **accept** (the row stays as it is), or **review** (a person samples rows first). "Retire" means a reviewed one-off statement the owner runs, setting `is_active = false, is_current = false` for the rows in that group. It does not delete them, so it can be undone. No statement is included here on purpose. The owner writes and runs it after deciding.

| Group | What it is | May hold connector content? | Proposed handling | Reason |
|---|---|---|---|---|
| G1 probe | Synthetic rows from the one-brain smoke and isolation probes | No | Retire | Test data. It has no value for customers and makes recall noisier. |
| G2 connector_confirm | "Confirmed action: …" rows written after a user confirmed a connector action | Yes. Labels can name records, recipients or deals | Review, then retire by default | These are the rows the lineage work exists for. A disconnect can never remove them. Sample about 20 rows per affected org (audit query 3). If the labels are generic ("send email", "create task"), the owner may accept them as action history instead. |
| G3 external_content | `untrusted_external`: connector or document content | Yes | Retire | This is source content by definition, already capped at low confidence. Without a tag it cannot be purged per source. |
| G4 outcome | Workflow and turn outcomes (`outcome_learning`, `learn_outcome:`) | Rarely. Status text, sometimes a step error | Accept, spot-check errors | The rows describe Gravitre's own runs. Spot-check rows containing "Errors:" for provider response text. |
| G5 promotion_v4 | Promoted org patterns (glossary, workflow, decision, response) | No. Built from Gravitre's own tables | Accept | These are aggregates of internal activity, not records from any source. |
| G6 user_direct | User statements and user-confirmed facts | No | Accept | The user said it. Disconnecting a source does not change that. |
| G7 model_inference | The model's reading of a conversation turn | Possibly, if the turn quoted connector data | Review | Sample per org. If samples quote connector records, retire. Otherwise accept. |
| G8 unclassified | No `source_class` (written before 20260903120000) | Unknown | Review | Provenance is unknown. The purge already refuses to reveal these as superseded values. |

Customer observations (`entity_observations`) written before the migration are untagged as well. When a vendor's last connection is removed, the purge removes them by vendor. While another connection of the same vendor is live, they are kept and counted as `entity_observations_unattributed` in the purge receipt. Proposed handling: **accept until that vendor's last connection is removed.** Before then, no row can be wrongly removed. The feature is off by default, so this set should be small or empty. Audit query 5 sizes it.

## What is already decided in code (not legacy handling)

- New connector-derived writes carry their connector once `MEMORY_SOURCE_LINEAGE_ENABLED=true`. A connector memory or observation that cannot name its connector is not written.
- User-confirmed email recipients and Slack channels (`org_entity_resolution_records`, integration `email` / `conversation`, source `parameter_ledger_confirmed`) persist through a disconnect. `tests/db/test_source_scoped_observation_purge_pg.py::test_full_disconnect_keeps_user_confirmed_recipients_and_channels` covers this.
- Superseded-value reveal only restores an older value with valid provenance that retention still allows (see the migration header). Legacy rows in G1, G2, G3, G7 and G8 are never revealed.

## Order of operations proposed

1. Owner authorizes the migration (checkpoint plan: `memory-lineage-migration-checkpoint-plan-2026-10-12.md`).
2. Run the audit and record the counts.
3. Owner decides each group above. Any retire statement is reviewed and run by the owner. It is not part of a migration.
4. Turn on `MEMORY_SOURCE_LINEAGE_ENABLED`.
5. Only after that, consider `SOURCE_PURGE_DRY_RUN=false`. That is a separate decision. No live purge is part of this PR.
