# Product experience acceptance matrix

Date: 2026-09-24. A–J functional roadmap is complete. This is **not** a new 3.0-K. Full Product Experience Contract (Section 0) is **not** accepted.

Do not collapse this table into one PASS.

| Surface | Status | Evidence class | Notes |
|---|---|---|---|
| Text conversation quality | PARTIAL | LIVE_API_PROVEN | Identity pin + Observation follow-up on `dd576514`; status-only vs identity fields on `0b879ec4` |
| Voice conversation quality | PARTIAL | LIVE_VOICE_PROVEN | Synthetic PCM confirm → WRITE → verify on `1f548ca8`. Physical mic HUMAN_EXPERIENCE_PENDING |
| Governed READ | LIVE_API_PROVEN | LIVE_API_PROVEN | F1 / listing / diagnostics. Contact count `f7d13fba` conv `278173be-…` Observation `hubspot.contacts.search` total 57 @ `2026-09-24T22:04:31Z` |
| Governed WRITE | LIVE_API_PROVEN / LIVE_VOICE_PROVEN | CI_PROVEN | HTTP spoken_mode `dd576514` contact `278972733388`. PCM `1f548ca8` contact `279209311173` |
| Repair | LIVE_API_PROVEN | CI_PROVEN | F2 sibling repair |
| Cross-system entities | LIVE_API_PROVEN | CI_PROVEN | Store join; no silent merge |
| Finished artifacts | CLOSED | LIVE_API_PROVEN | **Do not reopen.** `b6a9722c` CI_PROVEN + LIVE_API_PROVEN ([36226281760](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36226281760)). Presentation contract `9fcaa89c` CI_PROVEN ([36229510637](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36229510637)). Canonical `execution_result` only — no second artifact model. LIVE_UI_PROVEN pending owner-live frontend auth. |
| Computer Use | LIVE_API_PROVEN | LIVE_API_PROVEN | READ-only Chromium `browser_cdp` on `7ac66c36` conv `1526c728-…` Observation `feaf699f-…` two public pages + research_summary. Follow-up from persisted visits, obs_count=1. Latency cut on `6cf8ea33` conv `2163c13b-…` Observation `095d790f-…` `click_ms=105` `playwright_session_ms=1956` (still real goto+click, not httpx). Progress SSE not LIVE-proven. Governed interact WRITE mechanics remain `ecb86dcf`. |
| Cross-surface continuity | CODE_COMPLETE | LIVE_API_PROVEN | Same conversation/plan/pending/artifacts. Presentation consumes canonical `execution_result`. LIVE_UI_PROVEN pending owner-live frontend auth. |
| Proactive attention | LIVE_API_PROVEN | LIVE_API_PROVEN | Positive: conv `5cfc0c14-…` `notice_count=2` GA+GSC re-auth, `write_allowed=false` @ `4a1e84e9` `2026-09-24T15:25:22Z` |
| Latency | PARTIAL | LIVE_API_PROVEN | Catalog search **preserve** on `158c43eb` conv `7d6901ef-…` first useful **4803 ms** / completion **7615 ms**. Class C listing **preserve** ~4.1s / ~6.1s on `c29f12cb`. Computer Use first-nav **LIVE_API_PROVEN** on `6cf8ea33` conv `2163c13b-…` Observation `095d790f-…`: first useful **6512 ms** / completion **10045 ms** (was **13893 / 17025** on `158c43eb`). Playwright session **1956 ms** (`click_ms` **105**, `link_text` Learn more). Progress SSE **not present** on this spoken_mode probe — UX-only, not a latency claim. Follow-up obs_count=1; after-thanks URL resume **2471 ms**. |
| Human-device voice | HUMAN_EXPERIENCE_PENDING | BLOCKED_EXTERNAL | Manual procedure below |

## Manual production test (physical mic)

Proof class: HUMAN_EXPERIENCE. Do not label synthetic PCM as this.

1. Signed-in production app, isolated org `f07e57c0-1501-4000-8000-c04e57a00001` only.
2. Start a **new** voice conversation.
3. Speak a unique placeholder HubSpot contact (`@alpha.test.gravitre.app`).
4. Confirm the approval repeats the exact name and RFC email.
5. Say “yes maybe” — expect no provider WRITE.
6. Say “yes, create it.”
7. Confirm one HubSpot create, Observation, terminal plan, accurate spoken result.
8. Repeat “yes” — zero duplicate WRITEs.
9. Ask whether the contact was created — answer must use the prior Observation.
10. Record conversation id, plan id, HubSpot id, timestamps.

Cleanup (Cesar approval required): HubSpot `278972733388`, `279209311173`, `279246127081`. Do not silent-delete.

## HubSpot contact count READ (`f7d13fba`) 2026-09-24

- HTTP spoken_mode Class C. Isolated org `f07e57c0-1501-4000-8000-c04e57a00001`.
- Conversation: `278173be-8ce1-4763-a869-9da7dd8d2c20`
- Plan: `bef07e98-645d-4653-ac66-90ff804be164` `source=listing_f2_read` `terminal_status=completed`
- Observation: success, `action_key=hubspot.contacts.search`, `result_count=57`, `provider_invoked=true`
- Spoken: “This HubSpot account has 57 contacts.”
- Tools: none (`searchKnowledgeBase` not selected). No WRITE.
- Before (`491ed409`): first useful 23761 ms, completion 48490 ms, tool `searchKnowledgeBase`.
- After (`f7d13fba`): first useful 11315 ms, completion 15525 ms.
- CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36063508675
- `/health` SHA `f7d13fbab47f8d58dbc3bd03f3fb47a32efe82d3`
- Evidence class: **LIVE_API_PROVEN** (not LIVE_UI_PROVEN). Matrix docs SHA `d30d3a4a` is not a capability release.

## Phrase-bank Class A + Observation identity (`0b879ec4`) 2026-09-25

- Serving SHA `0b879ec4577965ca3029bacd13e54d218192c0f6`
- CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36068439450
- Class A prompt is Intent Gateway phrase_bank. Composer LLM skipped. Model request count 0. Cached input tokens N/A.
- Class A: first useful **4551 ms**, completion **7638 ms**, excerpt “Hey — I'm here. What do you want to get done?”
- Class B conv `59120b14-8235-4279-9692-2ef0cbee1120` plan `0a3e4716-397e-47f6-bb41-c261e4865135` pending `executed` / COMPLETED / Observation verified. Status-only: “Yes — that contact was created and verified.” (`used_email=false`, `used_provider_id=false`, 5014 / 8217 ms). Identity: email `gravitrepcmwrite20260924181201@alpha.test.gravitre.app` + record `279246127081` (3150 / 5493 ms). No second WRITE.
- Class C regression conv `0ee198dd-d7e7-4e00-ba9c-c2daa53b6c2b` plan `595e83aa-c84f-43ee-92ab-b8dd43a8b76b` Observation `24b29190-c657-48c0-b295-e61855a76582` `hubspot.contacts.search` result_count **57**, spoken “This HubSpot account has 57 contacts.” Tools none. GET state `work_artifacts[0].kind=executive_report` exportable, reconstruct `execution_result.entity_id=595e83aa-…`. first useful 6636 ms / completion 8801 ms.

## Listing contact-count table artifact (`f522a717`) 2026-09-25

- Serving SHA `f522a7179707d40cf768b45b4c78dc8ffc466622`
- CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36081750627
- Railway: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36081750646
- Conversation: `fb03f3fe-0511-4d6c-8176-8b88952dc0e8`
- Plan: `cac365d0-6003-4d98-8c94-00be172284c1` `source=listing_f2_read` `terminal_status=completed`
- Observation: `fd95772b-c79c-4d21-b060-f10b841aa8e9` success, `action_key=hubspot.contacts.search`, `result_count=57`, rows `[{system:HubSpot, object:contacts, count:57, source:hubspot.contacts.search}]`
- GET `/api/assistant/conversation/{id}/state` `work_artifacts[0].kind=table` exportable; markdown includes `| HubSpot | contacts | 57 | hubspot.contacts.search |`
- Reconstruct `execution_result.entity_id=cac365d0-…` success true. No invented price.
- Resume “Show me that table”: HTTP 200, 7115 ms, spoken “This HubSpot account has 57 contacts.”, still **one** Observation, kind remains `table`. No WRITE.
- Evidence class: **LIVE_API_PROVEN** (not LIVE_UI_PROVEN).

## READ-only Computer Use / browser_cdp (`7ac66c36`) 2026-09-25

- Serving SHA `7ac66c362e342cb58108d088a3744b3c78c1a341`
- Exact-SHA CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36116044917 PASS
- Prior gate `1a0dcfd5` CI https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36110712549 PASS (follow-up spoken was still PARTIAL on that SHA)
- Isolated org `f07e57c0-1501-4000-8000-c04e57a00001`
- Conversation: `1526c728-6352-4697-a4a2-1883e7802aee`
- Plan: `78854d2a-a0aa-4866-93da-e8b6791f34a6` `source=computer_execution` `execution_strategy=browser_cdp` `terminal_status=completed`
- Observation: `feaf699f-d143-4bc2-bdea-b8b6dbf0d061` success, `mode=playwright_session_read`, two visits (example.com goto, iana.org click_link Learn more)
- Artifact: `research_summary` exportable. Reconstruct entity `78854d2a-…`
- Follow-up “What was the second page URL? Do not browse again.” → `https://www.iana.org/help/example-domains` tools none, 3754/6002 ms
- “What was the title of the page we ended up on?” → `Example Domains` tools none
- After non-browser “Thanks…” (phrase-bank), same URL follow-up again, still tools none
- `obs_count_after_followup=1`. No searchKnowledgeBase. No WRITE. No second Chromium session
- Class: **LIVE_API_PROVEN**. Not HUMAN_EXPERIENCE_PROVEN. Not LIVE_UI_PROVEN. Interact WRITE remains gated.

## PCM confirm → WRITE → verify (`1f548ca8`)

- Conversation: `74ad31c7-d203-4591-8576-0426a19d8ccc`
- Plan: `29b751fd-7999-4cbe-8635-c6c59fed9202` `terminal_status=completed`
- Pending: `executed`
- Observation success: true
- HubSpot id: `279209311173`
- Email written: `gravitrepcmwrite20260924160401@alpha.test.gravitre.app`
- Ambiguous “Yes. Maybe.” refused
- Duplicate “yes”: “Done already. I won’t create a duplicate.”
- Follow-up used Observation (email + provider id)
- Artifact: `docs/delivery/gravitre-pcm-write-live.json`
