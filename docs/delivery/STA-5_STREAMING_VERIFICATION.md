# STA-5 — Real-time token streaming verification

**Linear:** [STA-5](https://linear.app/staqbot/issue/STA-5) · **Related:** [STA-151](https://linear.app/staqbot/issue/STA-151)  
**Verified:** 2026-06-16 · **Deploy:** `9263bdc` on `main`

---

## Requirement (STA-5)

Two-phase assistant streaming so guardrails fail before the HTTP stream opens, and provider tokens forward through the failover chain in real time.

| Phase | Implementation | Path |
|-------|----------------|------|
| Pre-flight | Guardrails + message build | `ModelRouter.prepare_stream()` |
| Stream | Provider chunks + failover | `ModelRouter.stream()` → `run_failover_stream()` |
| Client | SSE `text-start` / `text-delta` / `text-end` | `backend/app/routers/assistant.py` |

Cosmetic post-hoc chunking of `complete()` output is **not** used on the assistant chat path.

---

## Unit tests (edge-case failover)

| Test | File | Covers |
|------|------|--------|
| Primary fails → secondary streams | `backend/tests/services/test_failover.py` | `ProviderUnavailableError` failover |
| Two fail → third streams | same | Rate limit + unavailable chain |
| All providers fail | same | `AllProvidersFailedError` |
| Invalid response — no failover | same | `ProviderInvalidResponseError` |
| Open circuit breaker skips provider | same | Breaker + secondary success |
| Deltas + final response | `backend/tests/services/test_model_router.py` | `ModelRouter.stream()` |

Run:

```bash
cd backend && python -m pytest tests/services/test_failover.py tests/services/test_model_router.py -q
```

---

## Production smoke (STA-5 / STA-173)

`npm run smoke:ai-production:report` step **`assistant_chat`** asserts:

- SSE framing (`data:` + `[DONE]`)
- `text-start` and `text-end` events
- At least one `text-delta` with non-empty content (real token stream)

Latest: [`smoke-ai-production-latest.json`](smoke-ai-production-latest.json) — **15/15 pass** (2026-06-16).

---

## Sign-off

STA-5 acceptance criteria met in code and verified in production smoke. Issue closed in Linear as **Done**.
