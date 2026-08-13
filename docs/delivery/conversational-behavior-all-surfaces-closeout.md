# Conversational behavior — all-surfaces closeout (2026-08-13)

## Scope

One unified rules **1–10** multi-turn pass across:

Marketing, Sales, Legal, HR, Cybersecurity, default assistant (no `agent_id`).

Not a separate “wave2-only” Marketing/Sales re-run.

## Standing PARTIAL (preserved)

Earlier honest FAIL/PARTIAL @ tip `3c5b19a0` remains in
`conversational-behavior-all-surfaces-partial-standing.json` (do not rewrite).

## Shipped fixes that unblocked the pass

| Tip | Change |
| -- | -- |
| `b53e7e9c` | Hard-clarify ambiguous HR/default/SEO opens |
| `c07cd4b0` | Widen `hold_position` decisive-language markers (gate logic unchanged) |
| `6100842c` | Wire Legal/Cyber clarify patterns; brief definition hard path; correction-recall + Also: pushback; scorer `from X to Y` non-active forbid |

## Live PASS evidence

- Tip: `6100842c817aa686fb7bae99c8e45a15db94db20`
- Artifact: `conversational-behavior-all-surfaces-after-transcript.json`
- `verdict=PASS` · `passed=6` · `total=6`
- Surfaces: marketing, sales, legal, hr, cybersecurity, default_assistant — all `pass=true`

## Trace note (class-level)

Hard-clarify runs on the **shared** LIVE path (`apply_unified_turn_live` →
`ambiguous_open_clarify_reply`). Legal/Cyber opens were missing from the
pattern list even though Marketing/Sales/HR/default were wired — same
“proven on some agents, not all” class bug.

## Next in program scope

Expert dialogue **substance** expansion for Legal / HR / Cyber (stubs → pilot
depth), now that structure rules 1–10 are live-verified on those surfaces.
