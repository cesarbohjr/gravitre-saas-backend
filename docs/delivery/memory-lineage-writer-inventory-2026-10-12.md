# Memory lineage: writer inventory

Every code path that writes `agent_memories`, `entity_observations` or `entity_behavior_signals`, whether it is connector-derived, and how its lineage is carried. `backend/tests/services/test_memory_lineage_coverage.py::test_every_memory_writer_is_classified` scans `backend/app` for these writes. It fails when a writer is added or removed without updating the inventory in that test.

"Refused" below means: when `MEMORY_SOURCE_LINEAGE_ENABLED=true` and the write cannot name its connector, nothing is stored.

## Connector-derived (tagged)

| Writer | What it stores | Lineage |
|---|---|---|
| `chat_connector_execution_service._promote_confirmed_workspace_memory` → `promote_turn_memories` | Typed memories after a confirmed connector action | `source_connector_id` = the `connectors.id` the action ran through (`ExecutionResult.connector_id`). `source_record_ref` = the provider record id. Refused untagged. |
| `entity_observations.record_observations` (via `customer_observation_feed.handle_customer_message`) | Customer observations quoted from a customer message | `source_connector_id` = the outbox event's `connector_id`. Refused untagged. Retried without the column before the migration. |
| `compute_entity_behavior_signals` (SQL, daily scheduler) | Behaviour signals aggregated from observations | Not taggable (an aggregate over every source of an entity). The purge drops all signals of any entity that lost an observation, and the next daily run rebuilds them from the observations that remain. |
| `promote_turn_memories`, any candidate with `source_class = untrusted_external` | Connector or document content | Tagged when the candidate or its act names a connector. Refused untagged. |
| `memory_extraction_service.extract_typed_memories_structured` | Candidates from an act result (`typed_memories`, `memory_content`, `external_memory_candidate`, outcome) | Each candidate inherits the act's connector unless it names its own. It never takes another connector's record ref. |

## Not connector-derived

| Writer | Why |
|---|---|
| `routers/agent_memories.py` → `create_agent_memory` | Per-agent memory API: what a user typed. |
| `agent_memory_service.remember_*` (via `learning_feedback_loop`) | Gravitre feedback, approval and prediction events. |
| `workflows/execution_engine_runtime.py` → `create_agent_memory` | Workflow id, run status and Gravitre step errors. A step error can include a provider's error message, so with lineage on the memory keeps the error count only (`_outcome_memory_insight`). Rows written before that are spot-checked by audit group G4. |
| `memory_promotion_service._write_memories` | Aggregates over glossary terms, workflow runs, query patterns and approvals. |
| `cognitive_turn_kernel.run_learn` → `promote_turn_memories` | Today its callers pass status summaries only. If an act result ever names a connector, its candidates inherit it. |
| `routers/ops_internal.py` (probes) | Synthetic smoke and isolation rows. |

## Related stores handled elsewhere

| Store | Handling |
|---|---|
| `org_entity_resolution_records`, `org_business_entity_bindings`, `org_business_entities` | `purge_connector_derived_data` (M1, applied) by vendor when no other live connection of the vendor remains. User-confirmed recipients and channels (integration `email` / `conversation`) are never matched by a vendor and persist. |
| `agent_knowledge_references`, `rag_*` | M1, by connector. |

## Read side (before and after the purge)

With `MEMORY_SOURCE_LINEAGE_ENABLED=true` (`backend/app/services/memory_source_liveness.py`):

| Reader | What is dropped |
|---|---|
| `search_agent_memories`, `search_department_memories` (RPC and fallback), `get_relevant_agent_memory` | Memories whose `source_connector_id` names a connector that is soft-deleted, has status revoked/disconnected/deleted/inactive/disabled, belongs to another org, or no longer exists |
| `recall_workspace` (and its history branch), `HybridMemoryService._query_agent_memories` | Same. These feed the cognitive kernel's RECALL (Chat and Voice) and the classical retrieval path |
| `entity_context_card`, `account_health.load_account_health` / `load_health_batch`, `recommendation_feed` accounts | Observations from such a connector, and the behaviour signals of an account whose every observation read came from one |

Untagged rows are kept. A failed liveness read drops the memories (and tagged observations and all signals) for that read.

On a disconnect (route `DELETE /connectors/{id}`, `DELETE /sources/{id}`, and the `source.disconnected` handler) the org's context epoch is bumped. It is part of the retrieval, instant-answer (tier 0) and source-summary cache keys and is checked by the connector read-result cache, so those miss on every replica that shares Redis. In-process caches for the org (connector read results, connected-integration snapshot, account names, org context, intelligence projection) are cleared on the replica that handled it.

## Residual (owner to decide; not changed here)

- A connector re-added under the same name reuses its row (`deleted_at` is cleared), so memories tagged with it become readable again unless the purge already removed them. The data comes from the same account the user re-authorised; the purge (dry run off) is what removes it for good.
- Without Redis, the context epoch is per process: other replicas' caches expire on their own TTLs (retrieval 5 min, instant answers 1 h unless their source documents changed, connector reads 90 s).
- A connector whose status is `error` (for example a refresh failure) is not treated as revoked.

- `org_memory_entity_embeddings`: opaque HMAC tokens of entity names, which expire after 30 days. They are not purged per connector and age out instead.
- `org_entity_relationships`: built from glossary terms and departments. These are not connector records.
- Workflow-outcome step errors (above) may quote a provider's error text. They are untagged because a run can touch several connectors.
- M1 deletes an entity that is bound only to the disconnected vendor, which cascades to all of its observations. Today observations are only filed against entities bound to the same vendor that produced them (HubSpot), so no other source's observations are lost this way. That changes if a second observation source starts filing against HubSpot-only entities.
