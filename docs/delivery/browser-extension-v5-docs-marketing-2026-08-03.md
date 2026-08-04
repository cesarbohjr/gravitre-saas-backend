# Extension v5 — docs & marketing (post live proof)

Date: 2026-08-04  
Build proof: Edge + Brave **in-browser** functional (enrich → write → workflows → chat/handoff → overlay)  
Artifact: `docs/delivery/browser-extension-v5-live.json`  
Tip-verify: `docs/delivery/browser-extension-v5-tip-verify.json`  
Tip `git_sha`: `e7ab5afaaad0dcb2e37216180f846d19608e3be7`

## Evidence pointers

- Edge confirm write: runId `f0f9ba3c-a909-4197-b797-cbc1a237edb5` (`source=browser_extension`)
- Brave confirm write: runId `2abd360b-8456-40b4-9a8d-ae06127e2c0b` (`source=browser_extension`)
- Edge chat: conversation `d7625307-c573-4bed-9788-52824ea0692c`
- Brave chat: conversation `3a43c98a-53cc-4743-8562-67a4bdaaabb3`

## Marketing honesty

- Supported: **Chrome / Edge / Brave** (same MV3 pack).
- Explicit exclusion: Firefox, Safari, mobile.
- CWS CTA: live page still falls back to **Install guide** until `NEXT_PUBLIC_CHROME_WEB_STORE_URL` is set (listing URL not wired; do not claim store install until env is live).
- v6 remains gated closed — no agentic DOM marketing claims.

## Updates already on main

- Setup guide + FAQ + marketing name Chrome / Edge / Brave.
- Extension install helper prefers CWS URL when env is present; otherwise setup guide.
