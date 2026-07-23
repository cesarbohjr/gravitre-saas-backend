# LLM quality test suite (standing)

Permanent category **distinct from** connector functional pytest. Run on **every model tier, Module D spec, or unified-prompt change** — not only at Phase 4 cutover.

## Suites (existing batteries)

| Suite | Script | What it guards |
|-------|--------|----------------|
| Knowledge boundary / fabrication | `scripts/verify-unified-turn-phase2-live.py` (combined) | No invented metrics or connector results |
| Persona / output consistency | `scripts/verify-unified-turn-persona-drift-live.py` | Voice drift over multi-turn |
| Pending / write authority | `scripts/verify-unified-turn-pending-fix-targeted-live.py`, Phase 4 monitor | Approval and pending-state behavior |
| Mapper ambiguity (STA-305) | `scripts/verify-unified-turn-phase4-live.py` | Tool selection under narrowed catalog |
| TTFT / latency | `scripts/verify-unified-turn-task-ttft-live.py`, `verify-unified-turn-ttft-breakdown-live.py` | Responsiveness regressions |

## Gap — not yet covered

| Suite | Status | Action |
|-------|--------|--------|
| **Prompt injection resistance** | **NOT RUN** | New battery: crafted user content attempting to bypass write-authority / system instructions on unified-turn live path |
| Automated trigger on prompt change | **PARTIAL** | Wire `unified-turn-phase4-cutover.yml` + doc checklist; add path filter on `module_d_unified_voice_spec.py` |

## Evidence bar

Same as `docs/ENGINEERING_STANDARDS.md`: PASS requires prod `audit_events` or committed `docs/delivery/*-live.json` with timestamp and SHA — not pytest alone.
