# Product experience acceptance matrix

Date: 2026-09-24. A–J functional roadmap is complete. This is **not** a new 3.0-K. Full Product Experience Contract (Section 0) is **not** accepted.

Do not collapse this table into one PASS.

| Surface | Status | Evidence class | Notes |
|---|---|---|---|
| Text conversation quality | PARTIAL | LIVE_API_PROVEN | Identity pin + Observation follow-up on `dd576514`; filler drafts removed in `4a1e84e9` |
| Voice conversation quality | PARTIAL | LIVE_VOICE_PROVEN | PCM stage + ambiguous refuse + confirm→canonical WRITE **attempt** on `4a1e84e9`; verified provider success **not** demonstrated (ASR email invalid) |
| Governed READ | LIVE_API_PROVEN | CI_PROVEN | F1 / listing / diagnostics, isolated org |
| Governed WRITE | LIVE_API_PROVEN | CI_PROVEN | HTTP spoken_mode on `dd576514` contact `278972733388`. PCM verified WRITE: not proven |
| Repair | LIVE_API_PROVEN | CI_PROVEN | F2 sibling repair |
| Cross-system entities | LIVE_API_PROVEN | CI_PROVEN | Store join; no silent merge |
| Finished artifacts | CODE_COMPLETE | CI_PROVEN | `executive_report` / `table` / `brief` / `action_plan` / `research_summary` bound to Observation. LIVE_UI_PROVEN: BLOCKED_EXTERNAL (expired trial) |
| Computer Use | CODE_COMPLETE | CI_PROVEN | Strategy classifier + existing browser-agent READ. Interact flag off. No paid CDP. No live headful PASS |
| Cross-surface continuity | CODE_COMPLETE | LIVE_API_PROVEN | Same `conversation_id` / `plan_id` / pending / artifacts. Contracts: `docs/delivery/gravitre-product-experience-contracts.md` |
| Proactive attention | LIVE_API_PROVEN | LIVE_API_PROVEN | Honest zero-notice (prior). Positive: conv `5cfc0c14-ff78-4608-bfc5-e6764d51e0d2` `notice_count=2` GA+GSC re-auth, `write_allowed=false` @ `4a1e84e9` `2026-09-24T15:25:22Z` |
| Latency | OPEN | LIVE_API_PROVEN | Metric B verified WRITE ~25.6s on `dd576514`. Filler no longer counts as first useful speech. SLO 5s/8s not met |
| Human-device voice | HUMAN_EXPERIENCE_PENDING | BLOCKED_EXTERNAL | See manual procedure below |

## Manual production test (physical mic)

Proof class: HUMAN_EXPERIENCE. Do not label synthetic PCM as this.

1. Signed-in production app, isolated org `f07e57c0-1501-4000-8000-c04e57a00001` only.
2. Start a **new** voice conversation (do not reuse a completed WRITE conversation).
3. Speak a unique placeholder HubSpot contact (new email under `@alpha.test.gravitre.app`).
4. Confirm the spoken approval repeats the **exact** name and email.
5. Say “yes maybe” — expect no provider WRITE.
6. Say “yes, create it.”
7. Confirm one HubSpot create, canonical Observation, terminal ExecutionPlan, accurate spoken result.
8. Repeat “yes” — zero duplicate WRITEs.
9. Ask “did that contact already get created?” — answer must use the prior Observation.
10. Record conversation id, pending/plan ids, HubSpot contact id, and timestamps.

Do not delete contact `278972733388` without Cesar’s approval. Record any additional PCM-created placeholder ids for authorized cleanup.

## PCM confirm evidence (not verified WRITE success)

- SHA: `4a1e84e91998d59c414fd98df7406a288fe91cf9`
- Conversation: `cbbe93e6-4648-436d-a953-be20f2b28242`
- Plan: `8fa9ecd9-4404-4e2c-bee2-cdf1afb07973` `terminal_status=failed`
- GET `/state` 200
- Confirm speech triggered HubSpot create; provider: invalid parameters (spoken-word email)
- Follow-up: “No. The last HubSpot create attempt failed validation…”
- Artifact: `docs/delivery/gravitre-pcm-write-live.json`
