# Memory hardening — Phase 0 honest audit

**Date:** 2026-09-03 · **Program:** seven-type memory taxonomy hardening  
**Standing lessons applied:** Class A (real traffic vs probe), Class B (dual-path verification), Class C (mutation proof), organic-vs-probe-derived labeling, fix shared helper not call site.

## Pre-flight regression

| Check | Result | Evidence |
|---|---|---|
| CI on `main` | **GREEN** | Latest CI success on tip before work |
| Memory pytest battery | **52 passed** | `test_memory_recall_signal`, `test_workspace_memory_and_metrics`, cross-org isolation in `test_intelligence_learning_layer`, expiration, promotion thresholds, v4 read path |
| Cross-org isolation | **PASS (pytest)** | `test_agent_memory_cross_org_isolation` |

## 1. Changed-fact behavior per type (pre-hardening → post-hardening)

| Type | Pre-hardening (real code) | Post-hardening |
|---|---|---|
| **preference** | Insert-only; duplicate rows; latest wins by `created_at` sort only | Temporal supersede on `memory_key`; prior value in `agent_memory_history` |
| **decision** | Same insert-only | Same temporal supersede |
| **relationship** | Same insert-only | Same temporal supersede |
| **procedural** | Same insert-only | Same temporal supersede |
| **outcome** | Insert-only append | Append-only (structured payload, no transcript replay) |
| **episodic** | Insert-only append | Append-only |
| **working** | Accepted on write path; not long-term typed set | Append-only; not superseded |

**Honest gap closed:** No type had genuine temporal history before; Knowledge Fabric documents had `valid_from`/`superseded_*` but `agent_memories` did not.

## 2. Structured vs raw transcript storage

| Type | Pre-hardening | Post-hardening |
|---|---|---|
| episodic / working | Mixed; kernel hybrid path may store raw snippets | Structured extraction via `memory_extraction_service` when promoted from act |
| outcome | **Raw transcript replay** — `Outcome (event): {message[:500]}` | Structured `{event, status, action, error}` summary; message only as `context_hint` when summary empty |
| preference / decision | Usually explicit typed content | Structured payload + explicit user patterns (ICP range) |
| relationship / procedural | Explicit promotions | Unchanged; temporal key added |

## 3. Validation before long-term standing knowledge

| Gate | Pre-hardening | Post-hardening |
|---|---|---|
| Promotion queue | `memory_promotion_service` manual approval (0 adjudicated rows) | Unchanged — orthogonal path |
| Turn promote path | Confidence float only; no source class | `memory_contamination_guard.validate_memory_write` — source_class + confidence cap |
| Untrusted external | None | Capped ≤45, `memory_caution` on write/recall, injection heuristic |
| Module C recall labels | Not on memory rows | `attach_recall_honesty` on every `recall_workspace` row |

## 4. Reachability and volume (organic vs probe)

From `memory-hardening-assessment.md` + instrument gap closure @ `9222036d`:

| Metric | Value | Label |
|---|---|---|
| `agent_memories` rows (all orgs) | 13 | **probe-derived** |
| Real org rows | 1 | **organic (minimal)** |
| Agents with `use_memory` | 0 / 146 | organic adoption off by design (Option B) |
| Workspace recall | Runs every kernel turn | organic path, often `total=0` in real orgs |
| Per-turn signal | `memory.recalled` + `memoryRecall` | instrument @ `9222036d` |

**Phase 1–3 live proof:** Deliberate **probe-labeled** rows in isolated smoke org `f07e57c0…0001` (same discipline as `prove-memory-recall-live.py`). Organic proof accrues from 2026-09-03 onward via `memory.recalled`; current organic volume is insufficient for ICP-change history proof alone.

## Architectural compliance

- Extends existing `agent_memories` + `workspace_memory_service` + `CognitiveTurnKernel` LEARN/RECALL
- No third-party memory product
- No parallel memory system
- Shared helpers: `memory_temporal_service`, `memory_contamination_guard`, `memory_extraction_service`, `memory_lifecycle_service`

## Phase 4 lifecycle

- Deactivate: `memory_lifecycle_service.deactivate_memory` / `forget_by_key` / `apply_forget_request` — deterministic `is_active=false`, not model discretion
- Composes with org scoping: all queries filter `org_id`; cross-org isolation tests re-run in pytest + live probe script
