# Unified turn — Phase 2 (batteries + cutover gates)

## Scope (program prompt)

Validate the unified reasoning path against every existing battery **before**
Phase 3 TTFT streaming or Phase 4 cutover. With LIVE cutover already on tip,
targeted cases still require `unified_turn.live.completed` / shadow audits and
Module D–shaped replies.

| Gate | Bar |
|------|-----|
| Pending-reply | **24/24** |
| Conversational path | **20/20** |
| Catalog leak / status-check / stale-plan | Live cases in battery script |
| STA-305 omit-detail | Live Slack create ≠ list channels |
| Knowledge-boundary ("0 recent runs") | Must not fabricate; escalate or admit gap |
| **Imperfect input (≥15)** | Typos / missing words / fat-finger / voice-garble — recover intent silently; never echo typos; never “I think you meant…” |
| Full email flow | Multi-step (PARTIAL until full multi-turn script) |
| Persona drift 30-turn | Required by prompt; tracked until wired |
| TTFT &lt;200ms streaming | **Phase 3** — reported as proxy only in Phase 2 |
| Cutover / remove old pipeline | **Phase 4** — blocked until Phase 2+3 clean |

## Imperfect input (architecture proof)

Belongs to the **reasoning call’s input understanding**, not Module D voice
output style — but is specified in Module D’s system instruction
(`module_d_unified_voice_spec.py`) next to knowledge boundaries, and verified
in this Phase 2 battery.

The classical `chat_action_mapper.py` regex/exact-match path cannot pass this
class by design. A clean imperfect-input pass is independent proof the
single-reasoning-call replacement is working.

Cases cover: common misspellings (`sned emial`, `creat a contct`, `aprove`,
`shedule`), missing/disordered phrasing, fat-finger patterns (`creaet`,
`connectr`), mixed correct+garbled, and ≥3 rough voice-transcription lines
(fillers `um`/`so`/`yeah`, run-ons).

## Run

```bash
python scripts/verify-unified-turn-phase2-live.py
```

Artifact: [`unified-turn-phase2-battery-live.json`](unified-turn-phase2-battery-live.json)

Status board: [`unified-turn-phase2-live-status.md`](unified-turn-phase2-live-status.md)

## Standing rule

`catalog_write_authority`, approval, Module A unchanged. Until Phase 4 remove,
classical rollback remains available.
