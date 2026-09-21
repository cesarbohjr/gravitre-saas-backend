# AI chat release closure (2026-09-20)

Incident investigation complete. Kernel restore `42fadd61` remains in production tip **`53a374c1`**. This file is the closure record, not a 3.0 kickoff.

## 1. Production SHA reconciliation (checked 2026-09-20T18:28Z)

| Surface | Value |
|---------|--------|
| origin/main | `53a374c13376be865ecad5338003bd821bc45d48` |
| Local HEAD | `53a374c13376be865ecad5338003bd821bc45d48` |
| Railway `/health` | **`53a374c1`** `status=ok`, db/cache healthy |
| Vercel production | **`53a374c1`** `dpl_8JPmpwnf2UoSZNZvU8pUzEquHdLh` |
| Flags | `ai_disabled=false`, `unified_turn_live_enabled=true` |

**Pair:** frontend `53a374c1` + backend `53a374c1`. Contracts compatible (same commit). Prior split (Railway `42fadd61` / Vercel `e2ca5441`) is closed.

| Historical SHA | Meaning |
|----------------|---------|
| `42fadd61` | Import-shadow fix; still the kernel patch inside `53a374c1` |
| `e2ca5441` | Prior frontend/harness; superseded |
| `635b8229` | Docs SHA-split; superseded |
| `53a374c1` | Current CI/HMAC/gate instrumentation release |

## 2. Required CI

Latest required `CI` on **`53a374c1`**: **PASS** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35528295674

Web, Backend pytest, Shared runtime text/voice gate, Integration Smoke: **success**. Billing E2E skipped. HMAC/governance tests were aligned, not disabled.

Local goldens this pass: **62 passed** (2.0-A invariants, F1 WRITE, Composer, write guard, shared typed+spoken plan-hold).

## 3. Authenticated browser

**AUTHENTICATED_BROWSER_BLOCKED**

Human: `https://gravitre.app/login` → operator SSO → `/ai` → Tests A–F. Do not paste credentials here.

## 4. Backend chat (isolated, same SHA)

**PASS** — `docs/delivery/gravitre-ai-chat-regression-live.json` conv `22020a9e-e486-41e0-ab09-28c4e42af2ce`

- A hello 200, first-delta 7231 ms, assistant present, no toast
- B follow-up hello same conversation, second user row, no duplication of assistant A
- C FAQ conversational
- D traffic → truthful source clarify
- E Send an email → Gmail vs draft; no send
- Persistence 10 messages, HTTP 200

Smoke: `f9dd81e8-…` `smoke-ok` @ `53a374c1`.

## 5. Post-fix voice PCM

**VOICE_AUDIO_BLOCKED** on `53a374c1`. Metric A @ `43570699` is historical only.

## 6. Greeting latency (instrumented, not optimized)

Shortcut + Composer LLM rewrite. Isolated first-delta ~6.9–7.2 s (n=2). Option A and Option B **not implemented** (quality unmeasured for B).

## 7. Shared-runtime contract

CI job **Shared runtime text/voice gate** **PASS**. Live typed **PASS**. Live voice PCM **BLOCKED**. AST import-shadow guard retained.

## 8. Rollback

Do not revert `42fadd61`. Rolling back `53a374c1` only for CI test patches would also drop the expanded gate job — prefer forward fixes.

## Remaining blockers (release vs incident)

1. Authenticated production `/ai` browser A–F  
2. Post-fix audible PCM @ `53a374c1`  
3. Greeting 7s first-delta (P2)  
4. 2.0 live goldens (traffic, recipes, WRITE compile, …)

**AI CHAT BACKEND RESTORED: YES**  
**AUTHENTICATED BROWSER VERIFIED: BLOCKED**  
**POST-FIX VOICE VERIFIED: BLOCKED**  
**REQUIRED CI: PASS** (`35528295674` / `53a374c1`)  
**SHARED RUNTIME RELEASE GATE: FAIL** (CI job PASS; browser + PCM still open)  
**READY TO RESUME 3.0: NO**

## 2026-09-21 2.0 remainder

HubSpot grounded READ **PASS** @ `b95a8735` (`191353b4-…`). K/L/M internal owners + Gmail F1 READ added in source (not yet this `/health` SHA until deploy). Authenticated browser and PCM **still BLOCKED**. Greeting latency unchanged until measured on the new SHA.

**2.0 PROGRAM COMPLETE: NO**  
**IMPLEMENTATION COMPLETE — EXTERNAL PROOF PENDING: YES**
