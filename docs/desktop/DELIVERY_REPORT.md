# Gravitre Desktop — delivery report (2026-08-10)

## Shipped in this tip

| Area | Path |
|------|------|
| Phase 0/1 lock + Rust honesty | `docs/desktop/PHASE0_SCOPE.md` |
| Tauri v2 companion scaffold | `apps/desktop/**` |
| Auth handoff (session reuse) | `apps/web/app/desktop/connect/page.tsx` |
| Marketing download (3 OS + version) | `/download`, home section, nav **Download** |
| Release manifest | `apps/web/public/desktop/latest.json` |
| CI build matrix | `.github/workflows/desktop-tauri.yml` |

## Architecture confirmations

1. **Native UI:** Vite/React companion — not embedded Next `/ai` routes.
2. **Deep-links:** `open_web_deep_link` → default browser → `https://gravitre.app/…` (browser cookies = no second login when already signed in).
3. **Auth:** Same Supabase access token + org as web/extension via `gravitre://auth`.

## Verification (evidence bar)

| Requirement | Status |
|-------------|--------|
| Summon ≤150ms (global shortcut → input-ready) | **PASS (warm)** — median 34ms / max 55ms in `%TEMP%\gravitre-desktop-summon.log` via `GRAVITRE_BENCH_SUMMON=1` (same show→input-ready path; Alt+Space blocked here by ChatGPT Classic — see `SIGNING_AND_LATENCY.md`) |
| Cold start measured | **NOT RUN** |
| Deep-link each 0.2 target | **NOT RUN** live — wired in code (`openDeepLink` / tray Approvals) |
| Native notification + approve/reject | **PARTIAL** — code wired to `/api/approvals` + notification plugin; CI binaries on draft release |
| Signed installers (3 platforms) | **NOT RUN** — certs not provisioned; checklist in `SIGNING_AND_LATENCY.md` |
| CI desktop matrix | **PASS** — https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31409015268 |
| Auto-update | **PARTIAL** — manifest at `/desktop/latest.json`; Tauri updater pubkey not provisioned yet |
| Marketing download section live | **Ship with web deploy** — version from manifest; OS highlight client-side |
| Zero 0.2 features built natively | **PASS (by design)** — Settings/Meson/Agents/full Activity/Billing only deep-link |

## Customer surfaces

**(a)** Explicitly requested in this conversation (desktop product + marketing download). No invented prices or Enable toggles.
