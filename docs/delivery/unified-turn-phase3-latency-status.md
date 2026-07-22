# Unified turn Phase 3 — first-token latency / streaming

Updated: 2026-07-22

## Gate from Phase 2

**PASS** — [unified-turn-phase2-live-status.md](unified-turn-phase2-live-status.md) / workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895)

## Live measurement (PASS with honest latency)

| Step | Status | Evidence |
|------|--------|----------|
| Prod tip | **PASS** | `git_sha=6a21e2ec…` @ `2026-07-22T10:32:12Z` |
| Streaming shadow | **PASS** | audits with `streamed=true` |
| TTFT numbers | **PASS (measured)** | [unified-turn-phase3-latency-live.json](unified-turn-phase3-latency-live.json) |
| 200ms brief target | **MISS** | p50 **1258ms**, min **474ms**, max **3437ms** (n=4 streamed) |
| Classical SSE still works | **PASS** | client first SSE 1.9–2.8s on same probes; Phase 2 batteries already green |

### Probe samples

| Message | `first_token_proxy_ms` | `latency_ms` | streamed |
|---------|------------------------:|-------------:|----------|
| Hey | 731 | 732 | true |
| Thank you | 474 | 476 | true |
| What's on your plate? | 1785 | 2013 | true |
| Send an email… | 3437 | 3706 | true |

## Notes

- Target &lt;200ms is a research aspiration; live gpt-4o-mini + tool schemas does not meet it yet.
- Phase 4 cutover may proceed with classical rollback; TTFT optimization is follow-on (model tier / tool narrowing / caching), not a silent claim of 200ms.
