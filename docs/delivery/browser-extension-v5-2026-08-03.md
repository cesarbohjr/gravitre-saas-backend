# Browser extension v5 — Chromium parity (Edge + Brave)

Date: 2026-08-03 (functional re-proof 2026-08-04)  
Baseline tip: `e7ab5afaaad0dcb2e37216180f846d19608e3be7`

## Scope

| In | Out |
|----|-----|
| Chrome, Edge, Brave — same MV3 `apps/extension` pack | Firefox, Safari, mobile |

No parallel action/identity/outcomes systems. Same Module A/B/C/D front doors.

## Proof model (raised bar)

For each of Edge and Brave:

1. Unpacked `--load-extension` launch (debug port ready).
2. CDP → Gravitree service worker (`background.js`).
3. Seed `chrome.storage.local` (JWT + org + apiBase).
4. In-browser functional: enrich → approve HubSpot write → workflows list → chat + handoff.
5. Overlay visual: inject `overlay.css` + named-step markup (`gvt-card` / `gvt-step` / `gvt-outcome`).

Shared tip API smoke (session + usage-signal) remains secondary.

## Live proof — PASS

Artifact: `browser-extension-v5-live.json`  
Tip-verify: `browser-extension-v5-tip-verify.json`  
Verified at: `2026-08-04T02:02:43Z`

| Case | Edge | Brave |
|------|------|-------|
| storageSeed | PASS | PASS |
| enrich (linkedin) | PASS (`source=browser_extension` path) | PASS |
| propose + confirm write | PASS runId `f0f9ba3c-a909-4197-b797-cbc1a237edb5` | PASS runId `2abd360b-8456-40b4-9a8d-ae06127e2c0b` |
| workflows list | PASS (20) | PASS (20) |
| chat page-context | PASS conversation `d7625307-c573-4bed-9788-52824ea0692c` | PASS conversation `3a43c98a-53cc-4743-8562-67a4bdaaabb3` |
| chat handoff (`/ai?c=` + prompt) | PASS | PASS |
| overlay visual | PASS | PASS |

Browsers: Edge `Edg/151.0.4129.59`, Brave Chromium `151.0.7922.71`, manifest `0.5.0`.

## CWS listing

Live `/features/extension` still shows setup guide / “not published yet” until
`NEXT_PUBLIC_CHROME_WEB_STORE_URL` is set to a real `chromewebstore.google.com` URL.
Functional Chromium parity does **not** depend on CWS publish.

## Smoke

```bash
python scripts/live-extension-v5-chromium-parity.py
```
