# Browser extension v5 — Chromium parity (Edge + Brave)

Date: 2026-08-03  
Baseline: v4 tip `bb56894f` / tip-verify `6b169e32`

## Scope

| In | Out |
|----|-----|
| Chrome, Edge, Brave — same MV3 `apps/extension` pack | Firefox, Safari, mobile |

No parallel action/identity/outcomes systems. Same Module A/B/C/D front doors.

## Proof model

1. Unpacked `--load-extension` launch on Edge and Brave (debug port ready = Chromium accepts the pack).
2. Deployed tip API smoke covering v1–v4 surfaces: session, usage-signal, enrich, workflows list, chat + handoff.

## Live proof — PASS

- Tip `git_sha=bb56894f06673d1c34dacf98481c1894c0e03efe`
- API v1–v4: session, usage-signal, enrich (linkedin, 4 suggestions), workflows list (15), chat page-context + handoff — all PASS
- Edge load: `Edg/151.0.4129.59` via `--load-extension` (manifest 0.5.0)
- Brave load: Chromium `151.0.7922.71` via `--load-extension` (manifest 0.5.0)
- Out of scope unchanged: Firefox, Safari, mobile

Artifact: `browser-extension-v5-live.json`
