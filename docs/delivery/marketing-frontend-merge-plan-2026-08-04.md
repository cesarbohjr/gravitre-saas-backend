# Marketing frontend merge plan — `marketing-page-assets` into `main`

Date: 2026-08-04

Merge instructions for pulling the v0 marketing/frontend work into `main` without
regressing the extension and connector work completed on `main` in parallel.

## Refs

| Side | Ref | SHA | Commits since base |
| --- | --- | --- | --- |
| Cursor | `main` | `88e1bd0e` | 20 |
| v0 | `marketing-page-assets` | `29e5b3e4` | 46 |
| — | merge-base | `4533ffbd` | — |

Both sides advanced past the base, so this is a genuine two-way merge, not a
fast-forward. Of 265 files touched across both sides, **9 overlap**.

Verification note: `remote.origin.fetch` in the v0 sandbox is pinned to an
unrelated branch, so `refs/remotes/origin/*` is stale there and reports phantom
divergence. The SHAs above were resolved with `git ls-remote`.

## Method

The conflict list below is not an estimate. It comes from an actual dry-run
merge in a scratch worktree (`git merge --no-commit --no-ff`), which was then
aborted and removed.

## Green zone — no overlap, no conflicts

- **`main`'s backend (19 files), `docs/` (35), `scripts/` (11), `supabase/`, `e2e/`** — the v0 branch touched none of these.
- **v0's `apps/web` marketing redesign (~109 of 113 files)** — `main` touched none of these.
- **Auto-merges cleanly:** `extension-page.tsx`, `content/docs/public/faq/index.mdx`, `content/docs/public/guides/how-to/browser-extension.mdx`.

## Conflict 1 — `chat-execution-panel.tsx` (silent feature regression risk)

Both sides edited this file for unrelated reasons:

- **`main`** added a `hosted` / `other` artifact split that renders hosted files through a new `FileReferenceChip` component (Phase 2/3 chat-artifacts, tip `e432a8b5`).
- **v0** restyled the flat artifact list into compact chips.

`file-reference-chip.tsx` is a **new file on `main`**, so it merges in cleanly as
an add. That is the trap: resolving this conflict with `--ours` leaves the
component present but unreferenced, and the **Files section disappears with no
build error and no type error**.

**Resolution:** keep `main`'s `hosted` / `other` structure and its
`FileReferenceChip` usage. Apply the v0 chip styling to the `other` branch only.
Do not resolve this file with `--ours` or `--theirs`.

## Conflict 2 — `apps/extension` (architectural divergence, not a merge)

This is not a text conflict that should be reconciled hunk by hunk.

- **`main`:** 21 raw-JS MV3 files, with `manifest.json` at the package root.
- **v0 branch:** a 61-file Vite + TypeScript rewrite, with the manifest moved to `public/manifest.json`.

Two specific hazards:

1. The v0 branch **deleted** `content/overlay.css`, `content/salesforce.js`, `content/shared.js`, and `content/slack.js` while `main` was actively modifying them (v4/v5/v6 work, Salesforce/Slack surfaces, Edge+Brave in-browser proof). These surface as delete/modify conflicts with **zero conflict hunks** — git presents no text to reconcile, so the wrong resolution erases proven work silently.
2. The v0 rewrite has **no per-site content scripts** — only a generic overlay. It does **not** preserve `main`'s site-specific Salesforce/Slack logic.

**Resolution: do not merge the extension in the same PR as the web redesign.**
Take `main`'s extension wholesale, ship the web work, and treat the rewrite as a
separate, deliberate decision. `sidepanel.html` is part of this same divergence
and is covered by the same instruction.

## Suggested sequence

```bash
git checkout marketing-page-assets
git merge main            # ours = v0 branch, theirs = main

# Defer the extension entirely; keep main's working, proven version:
git checkout main -- apps/extension

# Hand-merge this one file (do NOT use --ours):
#   keep hosted/other + FileReferenceChip, apply v0 chip styling to `other`
#   apps/web/components/gravitre/assistant/chat-execution-panel.tsx

git status                # confirm zero remaining U entries
```

## Pre-deploy verification

1. `/features` renders four product screenshots; `/features/technology` renders the approvals shot. (The governance section is excluded from `/features` by design.)
2. The chat execution panel still shows a **Files** section for hosted artifacts — this is the regression that produces no error.
3. The extension still builds via its **full** `build` script (`tsc && vite build && vite build --mode content`), and every manifest-referenced path exists in `dist/`. Running only `vite build` omits the content script.

## Carried-forward open item

`apps/web/lib/marketing-copy.ts` claims "60+ templates" and "6 department packs"
directly above a marketplace grid rendering **10 assets / 4 packs**. Left
unchanged because the true catalog size is not derivable from the code. If the
counts describe the full catalog rather than the visible sample, the copy and
the grid should be reconciled so they do not contradict each other on screen.
