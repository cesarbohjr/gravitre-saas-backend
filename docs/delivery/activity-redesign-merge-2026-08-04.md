# Activity redesign — merge + harness fix (2026-08-04)

## What v0 shipped (on `marketing-page-assets`)

- Viewport-locked two-pane Activity inspector (`fillViewport` AppShell)
- Keyboard listbox navigation, compact HubTabs / HubFilterBar
- FailureAlertsPanel toolbar + severity chips + internal scroll
- Shot fixtures for failure predictions
- `scripts/verify-activity-redesign.mjs` (structural scroll assertions)

## What blocked v0 completion

Verification chased `/e2e/shots/activity` and concluded hydration was broken. Real causes of the false negative:

1. **AppShell billing/auth bootstrap** still gated the shell unless `NEXT_PUBLIC_PLAYWRIGHT_E2E=1`, while `/e2e/shots` layout already allows plain non-production `next dev` without that flag — so SSR HTML could show chrome while client bootstrap never cleared (or list SWR never ran cleanly).
2. Prior chat-progress harness lesson: env-gated routes can return **HTTP 200 with a 404 body** when the flag is off — greps look empty even when components are fine.

Product `/activity` (logged-in) was not the broken path; the harness chase was.

## What we finished on `main`

1. Merged `origin/marketing-page-assets` activity commits (debug `console.log` + `dbg-activity.mjs` already removed on tip).
2. **AppShell:** bypass bootstrap in non-production when `pathname.startsWith("/e2e/")` **or** Playwright E2E flags — matches shots layout.
3. Activity Suspense fallback uses `fillViewport`.
4. Verify script writes under `docs/delivery/_artifacts/activity-redesign/` (not `/tmp/agent-browser`).
5. `tsc --noEmit` clean for the web app.

## Verify locally

```bash
cd apps/web && pnpm dev
# other terminal:
node scripts/verify-activity-redesign.mjs
```

Expect: list rows > 0 on `/e2e/shots/activity`, document does not scroll at 1440×900, panes scroll internally.
