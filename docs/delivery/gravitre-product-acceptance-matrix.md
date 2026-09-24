# Product experience acceptance matrix

Date: 2026-09-24. A–J functional roadmap is complete. This is **not** a new 3.0-K. Full Product Experience Contract (Section 0) is **not** accepted.

Do not collapse this table into one PASS.

| Surface | Status | Evidence class | Notes |
|---|---|---|---|
| Text conversation quality | PARTIAL | LIVE_API_PROVEN | Identity pin + Observation follow-up on `dd576514`; filler drafts removed in `4a1e84e9` |
| Voice conversation quality | PARTIAL | LIVE_VOICE_PROVEN | Synthetic PCM confirm → WRITE → verify on `1f548ca8`. Physical mic HUMAN_EXPERIENCE_PENDING |
| Governed READ | LIVE_API_PROVEN | CI_PROVEN | F1 / listing / diagnostics, isolated org |
| Governed WRITE | LIVE_API_PROVEN / LIVE_VOICE_PROVEN | CI_PROVEN | HTTP spoken_mode `dd576514` contact `278972733388`. PCM `1f548ca8` contact `279209311173` |
| Repair | LIVE_API_PROVEN | CI_PROVEN | F2 sibling repair |
| Cross-system entities | LIVE_API_PROVEN | CI_PROVEN | Store join; no silent merge |
| Finished artifacts | CODE_COMPLETE | CI_PROVEN | Bound kinds on durable deliverable. LIVE_UI_PROVEN: BLOCKED_EXTERNAL (expired trial) |
| Computer Use | CODE_COMPLETE | CI_PROVEN | Strategy + browser-agent READ. Interact off. No paid CDP. No live headful PASS |
| Cross-surface continuity | CODE_COMPLETE | LIVE_API_PROVEN | Same conversation/plan/pending/artifacts. Contracts published |
| Proactive attention | LIVE_API_PROVEN | LIVE_API_PROVEN | Positive: conv `5cfc0c14-…` `notice_count=2` GA+GSC re-auth, `write_allowed=false` @ `4a1e84e9` `2026-09-24T15:25:22Z` |
| Latency | OPEN | LIVE_API_PROVEN | HTTP Metric B ~25.6s (`dd576514`). PCM confirm collector ~69.9s (`1f548ca8`). SLO 5s/8s not met |
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

Cleanup (Cesar approval required): HubSpot `278972733388`, `279209311173`. Do not silent-delete.

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
