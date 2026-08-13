# Expert dialogue wave 2 — Legal / HR / Cyber (2026-08-13)

## Gate

All-surfaces conversational **structure** (rules 1–10) PASS @ `6100842c`
(`conversational-behavior-all-surfaces-closeout.md`). Substance expansion for
Legal / HR / Cyber was the next scoped step after Marketing / Sales / Finance pilot.

## Change

Expand `_EXPERT_DIALOGUES` stubs in `expert_dialogue_library.py` to pilot depth
(4 exchanges each) with practitioner markers (NDA carveouts / residual-use,
scorecard / adverse impact, MFA / phishing-resistant / bastion).

Live probe: `scripts/verify-expert-dialogue-live.py` (seeds Legal/HR/Cyber into
isolated smoke org when missing).

## Evidence

- Tip: `803c357f6d4cdcafb1a10a632dd3782be1bee936` (library tip `b8b40a72` ancestor; live tip advanced)
- Artifact: `expert-dialogue-after-transcript.json` (label `after`)
- Verdict: **PASS** `5/5` — marketing, sales, legal, hr, cybersecurity
- Scorer note: practitioner_framing widened for enforce/preferably/reduce/review (cyber false-fail on a good MFA reply)

## Deploy stamp

Library commit: `b8b40a722e472547ba7f9d1c335fb9e43d7de844`  
Live verify checkedAt: see artifact `checkedAt` field.
