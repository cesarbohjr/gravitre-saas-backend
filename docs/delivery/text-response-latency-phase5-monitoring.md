# Text-response latency — Phase 5 standing monitoring

**Status:** SHIPPED (tip pending deploy of this commit)  
**Checked:** 2026-08-06

## What was wired

1. **Golden signals API** (`golden_signals_service.py`) now returns live:
   - `ttft.wall_p50_ms` / `wall_p99_ms` / `wall_max_ms` from `unified_turn.live.*` audits
   - `mount_tti.ai_nav_to_interactive_p50_ms` from `platform.chat_mount_tti.sample`
   - Alert lists when thresholds breached
2. **Admin UI** (`golden-signals-panel.tsx`) shows TTFT p50, p99/max, mount nav→TTI p50.
3. **Alert script** `scripts/check-unified-turn-ttft-alert.py` — same pattern as fallthrough alert; writes `platform.unified_turn_ttft.alert` on breach.
4. **Mount sampler** — `chat-tti-mount-trace.py` writes `platform.chat_mount_tti.sample` each run.

## Thresholds (env-overridable)

| Signal | Default |
|--------|---------|
| `UNIFIED_TURN_TTFT_ALERT_P50_MS` | 1500 |
| `UNIFIED_TURN_TTFT_ALERT_P99_MS` | 5000 |
| `UNIFIED_TURN_TTFT_ALERT_MAX_MS` | 10000 |
| `CHAT_MOUNT_TTI_ALERT_MS` | 3000 (ai_nav→interactive) |
