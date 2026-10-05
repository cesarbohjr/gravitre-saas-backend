# Conversation + Voice Owner Acceptance

Status is **NOT RUN** until a human completes this against the production owner tenant.
Automated CI, fixture screenshots, synthetic PCM, and provider API success do not satisfy this gate.

## Preconditions
- Record deployed Git SHA and timestamp.
- Use the same production conversation ID across text and Talk where the UI supports it.
- Real owner account, real microphone/speaker, real connector.
- Run once on desktop Chrome and once on iPhone.
- Capture relevant `voice.output.*` / conversation telemetry for the same turns.

## Required sequence — each device
1. **Audible output:** Start Talk and ask a simple question. PASS only if the reply is physically heard.
2. **Five-turn continuity:** Complete five consecutive spoken exchanges without closing Talk. Names, constraints and corrections must survive.
3. **Text → voice:** In text state a name, decision and constraint. Switch to Talk and ask what was decided. All three must be retained.
4. **Voice reconnect:** Disconnect/reconnect Talk with the same conversation. Ask a referential follow-up. Prior state must remain.
5. **Voice → text:** Make a correction in Talk, return to text, and ask for the current decision. The correction must win.
6. **Backchannel:** While Gravitre speaks, say “mm-hm”/“yeah” naturally. It must not falsely stop.
7. **Barge-in:** While Gravitre speaks, say “wait, stop.” Audible output must stop promptly and the next turn must continue from what was actually heard, not the unplayed draft.
8. **Thinking pause:** Pause mid-request without yielding the turn. Gravitre must not repeatedly cut in.
9. **Governed tool:** Request a real write action. Gravitre must plan/clarify as needed, require approval, and not claim completion before execution/verification.
10. **Recovery:** Exercise one recoverable failure (connector unavailable/network retry where practical). The state must remain coherent and the failure must be explicit.

## Evidence record
For every step record: device/browser, conversation ID, turn ID if exposed, heard=yes/no, transcript, expected/actual behavior, latency observation, telemetry correlation, PASS/FAIL.

## Final gate
`OWNER_LIVE_ACCEPTANCE = PASS` requires all ten steps on desktop Chrome and iPhone with no silent reply, stale replay, cross-modal amnesia, false completion, or governance bypass.

Any missing evidence is **UNPROVEN**, not PASS.
