# Gravitre Desktop — Phase 0 / 1 lock

Status: **locked for build** · 2026-08-10  
Stack decision: **Tauri v2** (greenfield companion), with an honest Rust capacity caveat below.

## Honest toolchain tradeoff

| Fact | Implication |
|------|-------------|
| Repo had **zero** Rust/Tauri before this work | Greenfield native layer |
| This agent machine has **no `rustc` / `cargo`** | Local compile / 150ms summon measurement is **NOT RUN** here |
| Cursor can author Tauri Rust + CI can build via GitHub Actions | Scaffold + CI is the ship path |
| Electron would be more pragmatic for a JS-only day-to-day loop | Spec chose Tauri as the 2026 standard; we follow Tauri and keep Electron as a documented escape hatch if Rust capacity stays blocked |

**Escape hatch:** If signing + Rust CI stalls distribution, revisit Electron with the same Phase 0 feature split (do not widen native scope).

## 0.1 — Ships native (companion shell)

1. Chat (text + voice modality), primary surface — lightweight UI, **not** full `/ai` Next routes.
2. Global shortcut → compact always-on-top companion (Mac `Option+Space`, Windows `Alt+Space`, Linux `Alt+Space`).
3. System tray / menu-bar icon with connection/org status.
4. Compact activity feed → each row deep-links out for detail.
5. Native OS notifications from live notification stream.
6. Compact approval affordance (approve/reject) from notification / tray / feed.

## 0.2 — Deep-links out (never rebuilt natively)

Settings (all tiers / billing), Meson canvas, Connectors, Agents hub (roster/create/voice config), full Activity/Outcomes, marketing/pricing/upgrade.

## 0.3 — Not duplicated from browser extension

Page enrichment / overlays stay in Chrome extension only.

## 0.4 — Open questions (not assumed)

| Item | Test | Disposition |
|------|------|-------------|
| Department / response-style full pickers | Under 2s while working elsewhere? | **Ambiguous** — companion keeps session defaults; full tuners deep-link to web `/ai` |
| Agent roster switching | Set-aside work | Deep-link to Agents |
| Knowledge attach | Set-aside work | Deep-link to agent Knowledge |
| Billing / plan changes | Set-aside work | Deep-link (0.2) |

## Phase 1 — Architecture confirmations

1. **Frontend reuse:** Purpose-built Vite/React UI in `apps/desktop` calling backend APIs with Bearer + org headers. **Does not** embed the full Next app routes.
2. **Deep-links:** `tauri-plugin-shell` / OS open → default browser → `https://gravitre.app/...` with the **same Supabase session cookies** already on that browser profile (no second login when the user is already signed in on gravitre.app).
3. **Auth reuse:** Desktop does **not** invent a second identity. Handoff mirrors the extension: signed-in web `/desktop/connect` authorizes the running desktop app via `gravitre://auth` custom protocol (access token + org id + API/app bases). Token stored in the OS keychain/app store for the desktop process only.

## Phase 3 — Distribution realities

| Item | Status |
|------|--------|
| Unsigned CI artifacts (dmg/msi/AppImage) | Target via `.github/workflows/desktop-tauri.yml` |
| Apple Developer + Windows code-signing certs | **Required setup cost** — not provisioned in-repo; flag before claiming “signed” |
| Auto-update | Wired to Tauri updater + `public/desktop/latest.json` manifest |
| Marketing download section | Live on `/download` + home CTA; version from manifest |

## Verification labels (evidence bar)

- Summon ≤150ms: **NOT RUN** until measured on a built binary on each OS.
- Deep-links / native approval / installers: see delivery report for PASS / PARTIAL / NOT RUN.
