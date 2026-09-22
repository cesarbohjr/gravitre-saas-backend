# Computer / browser execution — architecture eval (no implementation)

**Reuse (required):** ExecutionPlan, conversation/task state, ActionSpec + HMAC, PendingAction, Observations, durable_checkpoint, Response Composer, AI Workspace.

**Existing code:** `browser_agent_service.py` — httpx public URL READ (SSRF-blocked), Playwright interact behind `browser_agent_interact_enabled=false` and `approval_id`. Headless, no live stream, not tenant VM isolation.

## Strategy, not a brain

`strategy=browser_cdp` | `strategy=computer_use` on the **same** plan step. Kernel still compiles capability → governance → execute → Observation.

Observation payload (canonical): `{success, url, action, screenshot_digest, dom_excerpt, cdp_trace_id, approval_id}`. Composer narrates; UI shows the live view iframe.

## Provider category (2026)

Evaluate hosted **headful CDP + live view + recording** (Browserbase, Steel, Kernel class) vs **visual computer-use APIs** (Anthropic/OpenAI/Gemini computer controls on a VM). Prefer: live view, session TTL, credential vault outside the model, replay for audit, no requirement that their agent SDK replace Gravitre.

Do **not** pick a vendor in this document.

## Controls

- Writes / form submits → PendingAction (same as API WRITE)
- Pause/resume = durable_checkpoint + freeze session
- Takeover = human CDP; Gravitre resumes from checkpoint
- Credentials = existing connector OAuth/vault; inject via browser profile API, never prompt tokens
- Failure = bounded Observation error, no infinite click loops
- Tenant isolation = one session per org/task

## What not to build

A Browser Agent product with its own planner, memory, or Composer.
