# Unified turn batteries — failure classification (no fixes applied)

Evidence artifacts (tip drift noted): conversational + pending on `git_sha=1c0eee8e…` (expect `c81d1200`); Phase 2 orchestrator on `c81d12009cd66e066831a2e20ef146cda189bd62` with mid-run tip drift.

## 1. Conversational path — 7 failures / 20 cases

Rubric: `scripts/verify-conversational-path-live.py` (`pass_if` lambdas). Transcripts from [`conversational-path-battery-live.json`](conversational-path-battery-live.json).

| Case | Class | User | Assistant (excerpt) | Why |
|------|-------|------|---------------------|-----|
| `mixed_hubspot_list` | **REAL REGRESSION** | haha nice, also can you check on that HubSpot list | You have a pending item… **abandon** or **hold** | Fresh conv (no seed). Rubric expects social ack + HubSpot/list language. Unified LIVE injected pending-interrupt copy instead of mixed social+task handling. conv `698b2680-…` |
| `mixed_slack` | **RUBRIC MISMATCH** | lol cool — also post a Slack message to #general saying hi | Slack isn't connected. Connect at /connectors… | Correct product behavior; rubric requires social ack token (`got it`, `on it`, …) **and** slack/#general — reply has slack/connectors but no ack word. conv `843e26e9-…` |
| `mixed_thanks_search` | **RUBRIC MISMATCH** | thanks, also search HubSpot for Acme contacts | I don't have enough information yet… missing detail | Task portion handled; rubric requires `welcome|glad|anytime|you bet` on thanks half — strict Module D ack list. conv `00e3479a-…` |
| `mixed_banter_gmail` | **RUBRIC MISMATCH** | you're funny — also draft a Gmail to demo@example.com | Thanks! I can draft that email… purpose and key points | Substantive draft ask + gmail; rubric requires `(ha|noted|welcome|hey|…)` — **Thanks** not in allowlist. conv `b6a280b6-…` |
| `mixed_hey_apollo` | **RUBRIC MISMATCH** | hey — also create an Apollo contact list named ConvPath Battery | Apollo connector isn't connected… | Apollo/list/connect covered; rubric wants extra social ack (`on it`, `got you`, …) beyond leading "hey" in user message only. conv `ece7613d-…` |
| `meta_what_can_you_do` | **REAL REGRESSION** | what can you do? | Apollo-centric tool catalog (search people, lists, sequences…) | Rubric requires operator framing (`connector`, `/connectors`, `Connected`, `approval`, `pack`). Reply is raw capability list — wrong persona surface under LIVE. conv `2f149cfd-…` |
| `pending_playful_1` | **REAL REGRESSION** | haha you're funny | Thanks! … anything else on your mind? | Conv seeded `awaiting_confirm` Gmail send. Rubric requires playful ack **and** pending reminder (`yes|cancel|approval|Gmail|…`). `pending_playful_2` PASS shows seed worked; LIVE dropped pending on turn 1. conv `140dc3ea-…` |

**Scorecard:** REAL REGRESSION **3** (`mixed_hubspot_list`, `meta_what_can_you_do`, `pending_playful_1`) · RUBRIC MISMATCH **4**.

---

## 2. Pending-reply classifier — 2 failures / 24 cases

Rubric: unrelated intents must include **`abandon`** and **`hold`**. Transcripts from [`pending-reply-classifier-battery-live.json`](pending-reply-classifier-battery-live.json).

| Case | Class | Seed | User | Assistant (excerpt) | Why |
|------|-------|------|------|---------------------|-----|
| `unrelated_connectors` | **REAL REGRESSION** | gmail pending | what connectors are Connected right now? | I don't have that information yet. Tell me the missing detail… | Expected pending-interrupt unrelated flow; unified LIVE treated as slot-fill, not abandon/hold. conv `acff9164-…` |
| `unrelated_how_many_runs` | **REAL REGRESSION** | orch pending | how many runs happened this week? | I don't have that count yet — run history wasn't retrieved… HubSpot | Answered substantively instead of abandon/hold gate; classical pending classifier bypassed under LIVE. conv `a360d42e-…` |

**Scorecard:** REAL REGRESSION **2** · RUBRIC MISMATCH **0** (22/24 PASS judgments align with product intent for seeded pending).

---

## 3. Imperfect input — 6 failures / 16 cases

Source: [`unified-turn-phase2-battery-live.json`](unified-turn-phase2-battery-live.json) (`182b91b3…` segment). Failure token in artifact: `shadow_outcome:conversational_reply` only (assistant copy + intent patterns satisfied).

| Case | User message | Assistant (excerpt) | Diagnosis |
|------|--------------|---------------------|-----------|
| `imperfect_creat_contct` | creat a contct named Jordan Lee in HubSpot | HubSpot isn't connected. Connect at /connectors… | **RUBRIC / taxonomy** — understood create+HubSpot+Jordan; audit `outcome_kind=conversational_reply` vs battery expecting taskish outcomes. Not typo echo, not map-fail. conv `2b5a8b5c-…` |
| `imperfect_creaet_list` | creaet an Apollo list called Q3 outbound | Apollo isn't Connected. Connect at /connectors… | Same — connector nudge classified `conversational_reply`. conv `aa17f243-…` |
| `imperfect_disordered_hubspot` | hubspot contact create for alex@example.com please | HubSpot isn't connected right now… create that contact | Same. conv `082cf34a-…` |
| `imperfect_doubled_drafte` | pleasse drafte a gmail to demo@example.com about pricing | I need the purpose and key points… Gmail isn't connected | Same (`conversational_reply`); clarifying + connect guidance is acceptable UX. conv `0a7750d6-…` |
| `imperfect_adjacent_senf_mesage` | senf a slack mesage to #general saying kickoff is at 3 | Slack connector isn't connected… | Same. conv `6d89ebc9-…` |
| `imperfect_voice_runon_list` | yeah so create a hubspot contact list named summer leads… | HubSpot isn't connected… create that contact list | Same. conv `d63814ea-…` |

**Real cause (one line):** Unified turn **understood** garbled/missing-token input and responded appropriately; failures are **`outcome_kind` audit labeling** vs Phase 2 judge at run time (`conversational_reply` not treated as taskish pass). Current repo `TASKISH_OUTCOMES` includes `conversational_reply` — **re-run on same tip may clear all six without product change**; optional product follow-up: map connector-nudge to `clarifying_question` / `connector_tool_proposal` for cleaner metrics.

**Not claimed:** STA-305 / persona-drift / full combined battery (items 3–6 deferred per program order).

---

## Program checklist (this pass)

| # | Item | Status |
|---|------|--------|
| 1 | Conversational + pending classification | **Done** (this doc + artifacts cited) |
| 2 | Six imperfect-input diagnoses | **Done** (§3 above) |
| 3 | STA-305 with connected Slack+HubSpot | **Harness ready** — `smoke-sta305-slack-draft.py` preflights isolated org connectors; exit **2 BLOCKED** with stderr if missing. **Re-run not executed** (needs live connectors in test org). |
| 4 | C/D latency | **In repo** — tier + embed gate + `warm_tool_document_embeddings()` on lifespan (`main.py`); see [`unified-turn-task-latency-cd-status.md`](unified-turn-task-latency-cd-status.md). **Prod re-measure** after deploy pin. |
| 5 | Phase 3 script → `live.completed` | **Fixed** — `verify-unified-turn-phase3-latency-live.py` + `scripts/unified_turn_audit_live.py`. |
| 3b | Persona-drift empty stderr | **Fixed** — live audit action + traceback on crash + missing-env message. |
| 6 | Full combined battery on stable tip | **NOT RUN** (per your gate; tip drift invalidated prior partial run). |
| 7 | Phase 4 sign-off | **NOT RUN** — batteries still FAIL / PARTIAL; no sign-off claim. |

**Before item 6:** set `EXPECT_SHA=<pinned tip>`, freeze Railway deploys, then `python scripts/verify-unified-turn-phase2-live.py`.
