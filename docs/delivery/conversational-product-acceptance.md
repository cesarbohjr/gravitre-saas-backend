# Conversational Product Acceptance

This gate closes the text + voice quality program only when both machine-verifiable and human-verifiable criteria are satisfied.

## Automated gate

Run:

```bash
bash scripts/run-conversational-product-acceptance.sh
```

The gate must pass all of the following:

- a new explicit write using the same connector action after a prior success creates a fresh action/approval instead of being rejected as a replay;
- bare lifecycle words such as `Stopped.` and `Failed.` are not surfaced as normal assistant dialogue;
- pending-action copy is human-readable and does not expose raw catalog action keys;
- the AI workspace does not carry stale failed/completed execution state into a new turn;
- approval presentation is derived from actual approval evidence;
- Pipecat emits an explicit per-turn completion marker while the websocket remains open;
- closing Talk is fallback-only, not the normal turn boundary;
- the live duplex path owns delivery so closing Talk cannot replay the assistant response;
- browser voice output telemetry reaches the backend persistence endpoint;
- partial TTS phrases remain provisional until a natural sentence boundary;
- live TTS output remains on the approved realtime model and higher-fidelity output contract.

The workflow `.github/workflows/conversational-product-acceptance.yml` runs the same gate on pull requests, main, and manual dispatch.

## Human production acceptance

Automation cannot truthfully certify physical audibility or subjective naturalness. After the prerequisite fixes deploy to production, run this owner-org acceptance:

1. Open `https://gravitre.app` in the real owner workspace.
2. Keep Talk open for the full test. Do not close or reopen the orb between turns.
3. Complete at least five consecutive voice turns.
4. Confirm each assistant reply is physically audible during the same open session.
5. Include at least one normal question, one correction/follow-up, and one action request requiring approval.
6. In text mode, complete:
   - one normal question;
   - one write requiring approval;
   - one `yes` approval;
   - one modified pending action;
   - one cancellation;
   - one second explicit write using the same connector action (for example, send another email).
7. Confirm the UI never shows contradictory states such as `Approval complete` together with `still needs approval`, or `Outcome completed` together with a failed result for the same action.
8. Listen specifically for:
   - sentence continuity;
   - natural pacing;
   - absence of chopped phrase boundaries;
   - no duplicated audio after closing Talk;
   - no delayed reply that appears only after remount.
9. Record the approximate UTC time and conversation/session ID when available.
10. Correlate the same turns with `voice.output.*` telemetry.

## Final acceptance states

Use only these statuses:

- `AUTOMATED_GATE_PENDING`
- `AUTOMATED_GATE_PASSED / HUMAN_PROOF_PENDING`
- `PHYSICALLY_PROVEN / QUALITY_REVIEW_PENDING`
- `ACCEPTED`

Do not use `ACCEPTED` unless:

- the automated acceptance gate passes on the exact production release head;
- the owner confirms five uninterrupted audible Talk turns;
- production telemetry confirms playback for the same session/turns with no contradictory missing/silent/blocked evidence;
- text action/approval scenarios behave correctly;
- the owner considers the selected voice quality acceptable for production.

## Scope

This acceptance gate validates integration of:

- repeat-action semantics;
- approval/result state truth;
- conversational response quality;
- realtime Talk lifecycle;
- TTS prosody and playback fidelity.

It does not replace provider-specific load testing, broad UI regression testing, or subjective voice selection A/B testing.
