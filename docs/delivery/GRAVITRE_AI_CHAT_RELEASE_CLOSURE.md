# AI chat release closure (2026-09-20)

Do not treat local `635b8229` as deployed. Railway kernel is still the import-shadow fix.

## 1. Production SHA reconciliation (checked 2026-09-20T17:49Z)

| Surface | Value |
|---------|--------|
| origin/main | `e2ca544135ed8fd7210f2408845862e9b6ce8182` |
| Local HEAD (this pass, unpushed until commit) | ahead of origin with docs SHA-split `635b8229` plus this closure |
| Railway `/health` | **`42fadd6179485971a36b5179834e3601514557b2`** |
| Vercel production | **`e2ca5441`** `dpl_Ah8SPrV3v79eRjyxKAw2csQzHKz9` |
| Flags | `ai_disabled=false`, `unified_turn_live_enabled=true` |

**Why frontend `e2ca5441` vs backend `42fadd61`:** Vercel deploys the Next app on every `main` push (docs/harness `e2ca5441`). Railway only moved the API when backend files changed; last kernel change is `42fadd61`. Later commits are docs/UX harness, not `execute_task_streaming`.

**API/SSE contract:** Compatible. No chat protocol change after `42fadd61`. Frontend `e2ca5441` is typecheck/harness.

**`635b8229`:** docs-only SHA split. Not deployed. Included in this closure commit if pushed.

## 2. Required CI (latest full run on origin)

Latest `CI` on **`e2ca5441`**: **FAIL** https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/35500286861  
- Web **PASS** (cognitive suite + build)  
- Shared runtime text/voice gate **PASS** (`106050747907`)  
- Backend pytest **FAIL** (same 15 as `42fadd61` `35497980128`)

This pass retested those 15 locally. They are **not** GitHub-green until this commit’s `CI` run finishes.

| Test | Assertion | Root cause | Predates chat outage? | Runtime? | Kernel? | Fix | Local retest |
|------|-----------|------------|----------------------|----------|---------|-----|--------------|
| `test_invoke_tool_resolves_capability_before_executor_lookup` | TypeError on `mock_exec.call_args[0]` | F1 WRITE HMAC runs after capability remap; mock never called | Yes (F1 write) | HMAC is real | No | Test patches write HMAC; HMAC tests remain | PASS |
| `test_backend_has_no_unguarded_dict_*` | `dict(x.get())` | Stored payload coercions | Yes | Yes (malformed JSON) | No | `safe_normalize_stored_dict` at owners | PASS |
| overlap `mismatch_cancels_and_reassembles` | `_prepare_turn_context(refined_query)` | Reassembly is E4 `_prepare_with_classification` | Yes (compile) | No (source shape) | Shared path | Pin cancel + compile reassembly | PASS |
| overlap flag-off serial | `ctx_start > last LIVE delta` | LIVE-on prefetch at line ~3385 even when `voice_context_overlap_v1` is off (avoid 8.5s double prepare) | Yes | Yes — overlap is intentional | Shared | Test now expects overlap when LIVE on | PASS |
| overlap one call site | `prepare_assistant_turn` count==1 | Second site is classification-enriched prepare | Yes | Dual sites are canonical | Shared | Count==2 + both closures | PASS |
| `test_execute_tool_call_delegates_to_registry` | `success is True` | F1 READ preflight before registry | Yes | F1 real | ReAct | Test isolates registry after non-F1 | PASS |
| `test_invoke_denies_agent_without_permission` | `permission_denied` | WRITE HMAC before permission | Yes | Both real | No | HMAC tests stay; this test binds passthrough HMAC to reach permission | PASS |
| `test_execute_plan_uses_bound_invoke_action` | `success is True` | WRITE compile without HMAC proof | Yes | F1 WRITE real | No | Test supplies compile proof; HMAC still required in prod | PASS |
| `test_f1_action_spec_is_single_canonical_owner` | `spec is catalog[key]` | `get_action_spec` cache returned a second walk | Yes | Identity SoT | F1 | Return catalog instance directly | PASS |
| Anthropic `test_extracts_system_and_normalizes` | `system == "SYS"` | F5 `cache_control` blocks | Yes | Prompt cache | No | Test accepts cached system blocks | PASS |
| slack invoke success / validation / retry | PREFLIGHT_REQUIRED | `slack.post_message` is F1 WRITE | Yes | HMAC real | No | HMAC covered in `test_phase_f1_write_preflight`; executor tests passthrough compile | PASS |
| `test_operator_turn_speaks_perceive_before_kernel` | kernel False at first audio | 3.0-C skips perceive on plan-without-execute | 3.0-C same window | Yes | Voice | Query is operator-task **without** plan-hold | PASS |
| `test_no_new_relationship_table_created` | `'business_entities' not in migrations` | Substring hit `org_business_entities` (2.0-B) | Yes | Schema exists | No | Forbid parallel `public.business_entities`; allow org fabric | PASS |

WRITE HMAC copy: uncompiled write now says “That write wasn't compiled…” (`PREFLIGHT_REQUIRED` code unchanged).

## 3. Authenticated browser

**AUTHENTICATED_BROWSER_BLOCKED**

Human action: sign in at `https://gravitre.app/login` with operator SSO (Google / GitHub / Microsoft), open `/ai`, run hello → hello → knowledge → traffic → email clarify → refresh → minimize/restore → expand/fullscreen. Do not paste credentials into this report.

## 4. Post-fix voice PCM

**VOICE_AUDIO_BLOCKED**

Preserve prior Metric A **p50 224 ms / p95 412 ms** @ SHA **`43570699`**, definition: speech-end to first audible PCM on that deployment only. It does **not** certify `42fadd61`.

## 5. 10.9s greeting (instrumented, not optimized)

Path remains: Intent Gateway **phrase_bank shortcut** → Composer `kind=shortcut` ∈ `MUST_COMPOSE_KINDS` → foundation-model rewrite of already-English bank copy.

Checkpoints now on shortcut complete `task_state.shortcut_latency_ms`: `client_ready`, `workspace_focus_resolved`, `intent_gateway`, `shortcut_composer_start`, `shortcut_composer_end`, `shortcut_first_text_delta`. `shortcut_composer_used_model` records whether the LLM ran.

Isolated evidence (`fd7ef9a1-…` @ `42fadd61`): first hello **10897 ms**, warm hello **5667 ms**. No F1/ReAct on hello. Workspace focus still loads before shortcut return.

Why the rewrite exists: Composer A13 — canned/shortcut kinds must not leak bank/internal copy. Quality: not A/B measured this pass; bank line and composed line were already similar (“Hey — I’m here…”).

**Option A — optimize current Composer shortcut:** keep `MUST_COMPOSE_KINDS`, use a cheaper/cached compose model, stream first token earlier, overlap focus load. Needs baseline + parity tests. **Not implemented.**

**Option B — existing deterministic Composer path:** same skip as `progress` / `plan_hold` when draft is already English and not `looks_like_raw_backend`. Preserves Composer ownership, drops the extra LLM. Needs A13 exception + parity. **Not implemented.**

No new hello handler. No second Composer. No behavior-changing latency ship.

## 6. Shared-runtime contract (mandatory CI job)

Job **Shared runtime text/voice gate** now runs typed shortcut + spoken plan-hold, typed normal, typed READ clarify, persist task_state, WRITE approval block, voice perceive-before-kernel (non-plan-hold), voice cancel, plus AST/import-shadow guards.

Voice-only cannot certify typed. API-only cannot certify browser.

## 7. Rollback

Kernel rollback of `42fadd61` re-breaks typed `/ai` (import shadow). Do not revert that commit. Frontend `e2ca5441` is unrelated to the chat outage.

## Remaining blockers

1. Authenticated production `/ai` browser  
2. Post-fix audible PCM @ `42fadd61`  
3. GitHub required `CI` green after this commit  
4. Greeting 10.9s (P2; options A/B only after baseline)

**AI CHAT BACKEND RESTORED: YES**  
**AUTHENTICATED BROWSER VERIFIED: BLOCKED**  
**POST-FIX VOICE VERIFIED: BLOCKED**  
**REQUIRED CI: FAIL** (origin `e2ca5441`; local 15 retested, not yet the GitHub required suite on this tip)  
**SHARED RUNTIME RELEASE GATE: FAIL**  
**READY TO RESUME 3.0: NO**
