# GRAVITRE — CAPABILITY GAP MATRIX

Behavioral benchmarks vs ChatGPT, Claude, Manus-style autonomy, Grok-style computer agents. **No cloning.** Isolated-org OAuth limits live business completion.

Legend: **matches** · **partial** · **architecture only, UX not** · **lacks** · **needs new execution strategy**.

---

## Competitive profile

| Behavior | Gravitre | Evidence |
|----------|----------|----------|
| Conversation fluency | **partial** | prod model tier **low**; no qualitative corpus this audit |
| Deep reasoning | **partial** | medium_high exists unused as default |
| Voice realtime natural | **partial** | HTTP SLO good; mic/WebRTC/barge-in UNKNOWN |
| Tool use (API) | **partial** | HMAC+F1 strong; catalog ≠ completed objectives |
| Autonomy (Manus-like) | **partial / lacks UX** | checkpoint LIVE; no artifact theater, weak parallel jobs UX |
| Browser/computer visible | **foundation only / needs strategy** | httpx READ; Playwright interact off |
| Speed | **needs optimization** | LIVE ~13.8s p50 |
| Memory continuity | **partial** | durable_checkpoint LIVE; cross-surface UNKNOWN |
| Long-running work | **architecture only** | Temporal configured; chat UX not a job runner |
| Visibility of steps | **partial** | SSE/tools; not a cloud desktop |
| Artifacts | **lacks** as first-class product | |
| Human takeover | **partial** | PendingAction; not pause-browser |
| Learning from outcomes | **weak** | events persist, consume weak |
| Governance | **matches / stronger** | HMAC, write_allowed, isolated org |
| Evidence-grounded | **partial** | Observations exist; internet research on; CEO live BLOCKED |

---

## Business objective benchmarks (isolated org)

| Scenario | Class | Why |
|----------|-------|-----|
| CEO: how is the business | **BLOCKED** | GA4+GSC pending_auth LIVE |
| Sales: deals at risk | **BLOCKED** | HubSpot OAuth human |
| Marketing: traffic drop | **BLOCKED** | same analytics OAuth |
| Support: churn risk | **UNKNOWN** | no run |
| Finance: overdue ∩ tickets | **UNKNOWN** | no run |
| Ops: find + recommend + follow-up | **UNKNOWN** | no run |
| Autonomous Ads campaign + approve | **BLOCKED** | Ads OAuth; WRITE PendingAction **exists** (architecture) |
| Voice equivalents | **PARTIAL** | same kernel; mic blocked; PCM STT only |

Do **not** score COMPLETED/VERIFIED. Catalog size is vanity.

Actions: ~755 registered / ~731 unique; F1 12 READ + 4 WRITE HMAC; live-proven **meaningful objectives**: **low % UNKNOWN numerator**.

---

## Completion scale (method)

ANSWERED / PLANNED / PARTIALLY_EXECUTED / COMPLETED / VERIFIED / FAILED / BLOCKED.

Current honest default for ambitious business asks on isolated org: **BLOCKED** (auth) or **PLANNED** (pending WRITE). Apollo `lists.create` path: **PARTIALLY_EXECUTED** (pending_auth, never sent) — LIVE 3.0-D.

---

## Computer / browser gap (not a build)

Reuse: ExecutionPlan, ActionSpec, Observations, PendingAction, SSE progress, durable_checkpoint.

Need: hosted browser/computer **strategy**, visual stream to workspace, pause/resume = same task id, HMAC-equivalent for DOM writes.

Do **not** add a browser agent brain.

---

## Manus-characteristic gaps (product behavior)

Visible progress (partial SSE), long-running (Temporal unused by chat UX), artifacts (lack), browser (foundation), parallel subtasks (code maybe, UX no), background continuation (partial), checkpoint (LIVE), takeover (approvals only), completion verification (QA hooks), self-repair (bounded, unquantified).
