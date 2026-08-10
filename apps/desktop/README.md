# Gravitre Desktop (Tauri v2)

Companion shell for macOS / Windows / Linux. Phase 0 scope: `docs/desktop/PHASE0_SCOPE.md`.

## What this is

- Compact, always-on-top companion (Alt/Option+Space)
- Tray presence, chat (text/voice modality), glanceable activity, native approvals
- Deep-links out to gravitre.app for Settings, Meson, Agents, full Activity, Billing

## Prerequisites

- Node 20 + pnpm
- Rust stable (`rustup`) + platform WebView deps
  - Windows: WebView2
  - macOS: Xcode CLT
  - Linux: `webkit2gtk` etc. (see Tauri docs)

This agent environment had **no Rust toolchain** — local `tauri build` was not run here. Use GitHub Actions (`.github/workflows/desktop-tauri.yml`) or install Rust locally.

## Develop

```bash
cd apps/desktop
pnpm install
pnpm tauri:dev
```

## Build

```bash
pnpm tauri:build
```

## Auth

1. Run the desktop app → **Connect with browser session**
2. Browser opens `/desktop/connect` (must already be signed in on gravitre.app)
3. **Authorize Desktop** → `gravitre://auth?…` hands the Supabase access token + org to the app

## Version / downloads

Marketing reads `apps/web/public/desktop/latest.json`. Keep that file in sync with `src-tauri/tauri.conf.json` `version` when cutting a release.
