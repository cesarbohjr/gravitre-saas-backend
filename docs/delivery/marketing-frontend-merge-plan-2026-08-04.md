# Marketing frontend merge plan — `marketing-page-assets` into `main`

Date: 2026-08-04

Merge instructions for pulling the v0 marketing/frontend work into `main` without
regressing the extension and connector work completed on `main` in parallel.

## Refs

| Side | Ref | SHA | Commits since base |
| --- | --- | --- | --- |
| Cursor | `main` | `88e1bd0e` | 20 |
| v0 | `marketing-page-assets` | `171e30c5` | 48 |
| — | merge-base | `4533ffbd` | — |

Both sides advanced past the base, so this is a genuine two-way merge, not a
fast-forward. Of 265 files touched across both sides, **9 overlap**.

The earlier v0 branch `v0/cesarbohorquezjr-4251-e2927faa` (`ee6f8dae`) needs no
separate merge: it is already an **ancestor** of `marketing-page-assets`
(`git merge-base --is-ancestor` confirms). Merging this branch carries it in.

Verification note: `remote.origin.fetch` in the v0 sandbox is pinned to an
unrelated branch, so `refs/remotes/origin/*` is stale there and reports phantom
divergence. The SHAs above were resolved with `git ls-remote`.

## Method

Nothing below is inferred from reading diffs. The full merge was executed in a
scratch worktree, both conflicts were resolved, the result was type-checked, and
`main` was type-checked in isolation to establish a baseline. The worktrees were
then removed. Two of the instructions exist specifically because the obvious
version of the command **failed** during that rehearsal.

## Green zone — no overlap, no conflicts

- **`main`'s backend (19 files), `docs/` (35), `scripts/` (11), `supabase/`, `e2e/`** — the v0 branch touched none of these.
- **v0's `apps/web` marketing redesign (~109 of 113 files)** — `main` touched none of these.
- **Auto-merges cleanly:** `extension-page.tsx`, `content/docs/public/faq/index.mdx`, `content/docs/public/guides/how-to/browser-extension.mdx`.

## Type-check baseline (read before you debug anything)

`apps/web` has **exactly 7 pre-existing `error TS2339`s**, all in
`components/gravitre/assistant/file-reference-chip.tsx` (lines 53, 61, 65, 66):
`Property 'title' / 'metadata' does not exist on type 'HostedFileRef | ChatArtifact'`.

These are present on **`main` alone, before any merge** — `HostedFileRef` lacks
fields that `ChatArtifact` has, and the union is dereferenced without narrowing.
The verified merge introduces **zero** new type errors.

So: 7 errors after merging is the expected, correct result. Do not attribute them
to the merge and do not "fix" them as part of it. An **8th** error, or any error
outside that file, means something in the merge went wrong.

## Conflict 1 — `chat-execution-panel.tsx` (silent feature regression risk)

One conflict hunk. Both sides edited the `ArtifactCards` return for unrelated
reasons:

- **`main`** added a `hosted` / `other` artifact split rendering hosted files through a new `FileReferenceChip` (Phase 2/3 chat-artifacts).
- **v0** restyled the flat artifact list into compact chips.

Two things make `--ours` actively dangerous here:

1. `file-reference-chip.tsx` is a **new file on `main`**, so it merges in cleanly as an add. `--ours` leaves it present but unreferenced.
2. The `hosted` / `other` filter declarations sit **outside** the conflict region and merge cleanly regardless. `--ours` therefore leaves them unused *and* falls back to `artifacts.slice(0, 6)` — rendering hosted files as generic artifacts.

The result is that the **Files section disappears with no build error, no type
error, and no lint error.** The exact resolution is given in the prompt below;
it has been type-checked.

## Conflict 2 — `apps/extension` (architectural divergence, not a merge)

This is not a text conflict to reconcile hunk by hunk.

- **`main`:** 21 raw-JS MV3 files, `manifest.json` at the package root.
- **v0 branch:** a 61-file Vite + TypeScript rewrite, manifest moved to `public/manifest.json`.

The two trees are almost entirely **path-disjoint**. Only three paths exist on
both sides — `popup.html`, `sidepanel.html`, `README.md` — and the two HTML files
are mutually exclusive entrypoints (`main` loads plain `popup.js`; the v0 branch
loads `/src/popup/main.tsx` through Vite).

Hazards:

1. The v0 branch **deleted** `content/overlay.css`, `content/salesforce.js`, `content/shared.js`, and `content/slack.js` while `main` was actively modifying them (v4/v5/v6 work, Salesforce/Slack surfaces, Edge+Brave in-browser proof). These surface as delete/modify conflicts with **zero conflict hunks** — git presents no text to reconcile, so a careless resolution erases proven work silently.
2. The v0 rewrite has **no per-site content scripts**, only a generic overlay. It is **not** a superset of `main`'s Salesforce/Slack logic.
3. Because the trees are path-disjoint, `git checkout main -- apps/extension` **is not sufficient on its own** — it only overwrites paths `main` has, leaving ~55 orphaned rewrite files (a second `public/manifest.json`, `vite.config.ts`, the whole `src/` tree) sitting alongside `main`'s extension.

**Resolution: do not merge the extension in the same PR as the web redesign.**
Take `main`'s extension wholesale using the exact 3-command sequence in the
prompt. This discards the v0 rewrite *including* its own bug fixes; that is
intentional and recoverable from branch history, since the rewrite never shipped
on `main` (`main` has zero files under `apps/extension/src`).

## Pre-deploy verification

1. `/features` renders four product screenshots; `/features/technology` renders the approvals shot. (The governance section is excluded from `/features` by design.)
2. The chat execution panel still shows a **Files** section for hosted artifacts — this is the regression that produces no error.
3. `apps/extension` is byte-identical to `main` (`git diff --quiet main -- apps/extension`) with no untracked strays.
4. The extension still builds via its **full** `build` script (`tsc && vite build && vite build --mode content`), and every manifest-referenced path exists in `dist/`. Running only `vite build` omits the content script.

## Prompt for Cursor

Self-contained: it states the invariants and the verified commands, so Cursor
does not need to infer intent from the diff.

````text
Merge the branch `marketing-page-assets` into `main` in this repo.

CONTEXT
Both branches moved since the merge-base. `main` (yours) has backend, docs,
scripts, supabase, e2e, and browser-extension work. `marketing-page-assets` (v0)
has an apps/web marketing redesign. Of 265 touched files only 9 overlap, so
almost everything auto-merges. Neither side may wholesale overwrite the other.
This plan was rehearsed in a scratch worktree and type-checked; the commands
below are the ones that actually worked.

STEP 1 — merge from the feature branch, so `main` stays clean until verified.

  git checkout marketing-page-assets
  git merge main          # ours = v0 branch, theirs = main

Expect exactly 6 conflicts: 4 in apps/extension/content/, plus
apps/extension/sidepanel.html and
apps/web/components/gravitre/assistant/chat-execution-panel.tsx.

STEP 2 — apps/extension: TAKE MAIN, DISCARD THE V0 REWRITE.
The v0 branch replaced the raw-JS MV3 extension with a Vite+TypeScript rewrite
and DELETED content/overlay.css, content/salesforce.js, content/shared.js, and
content/slack.js — files you were actively editing. They conflict with ZERO
conflict hunks, so git shows no text to reconcile and a careless resolution
silently erases your proven Salesforce/Slack work. The v0 rewrite has NO
per-site content scripts, only a generic overlay, so it is not a superset.

Use this EXACT sequence. `git checkout main -- apps/extension` alone is NOT
enough: the two trees are path-disjoint, so it leaves ~55 orphaned rewrite files
behind (a second public/manifest.json, vite.config.ts, the whole src/ tree).
`git rm -r` first also fails silently on unmerged paths — the working tree must
be removed before the index.

  rm -r apps/extension
  git rm -r -q --cached --ignore-unmatch apps/extension
  git checkout main -- apps/extension

Then confirm, before moving on:

  git diff --quiet main -- apps/extension && echo IDENTICAL
  git ls-files apps/extension | wc -l          # must print 21
  git status --porcelain apps/extension | grep '^??' | wc -l   # must print 0

Do not attempt to reconcile the two extension architectures in this PR.

STEP 3 — chat-execution-panel.tsx: HAND-MERGE. Do NOT use --ours or --theirs.
main added a `hosted`/`other` split rendering hosted files via a NEW component,
file-reference-chip.tsx. v0 restyled the artifact list into compact chips. Both
must survive. Note the `hosted`/`other` declarations sit OUTSIDE the conflict and
merge cleanly either way, so --ours leaves them unused AND falls back to
`artifacts.slice(0, 6)`, rendering hosted files as generic artifacts. The Files
section then disappears with NO build error, NO type error, NO lint error.

Replace the single conflicted region inside `function ArtifactCards` (everything
from `<<<<<<< HEAD` through `>>>>>>> ...`, keeping the surrounding
`return (` / `</div>` intact) with exactly this — main's structure, v0's chip
styling on the `other` branch. This version was type-checked:

    <div className="mt-3 space-y-2">
      {hosted.length ? (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Files</p>
          {hosted.slice(0, 8).map((artifact) => (
            <FileReferenceChip
              key={artifact.artifact_id || artifact.artifactId || artifact.title}
              file={artifact}
            />
          ))}
        </div>
      ) : null}
      {other.length ? (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Artifacts</p>
          {other.slice(0, 6).map((artifact) => {
            const href = artifactHref(artifact)
            const title = artifact.title || artifact.kind || "Artifact"
            const preview = artifact.preview?.trim()
            const external = href ? isExternalUrl(href) : false
            const Icon = artifactIcon(artifact.kind)
            const OpenIcon = external ? ArrowUpRight : ArrowRight

            const inner = (
              <>
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="min-w-0 truncate font-medium text-foreground" title={title}>
                      {title}
                    </span>
                    {artifact.kind ? (
                      <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                        {artifact.kind}
                      </span>
                    ) : null}
                  </span>
                  {preview ? <span className="mt-0.5 line-clamp-1 text-muted-foreground">{preview}</span> : null}
                </span>
                {href ? <OpenIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" /> : null}
              </>
            )

            const chipClass =
              "flex w-full items-center gap-2.5 rounded-md border border-border/60 bg-muted/30 px-2.5 py-1.5 text-left text-xs"
            const key = artifact.artifact_id || artifact.artifactId || title

            if (!href) {
              return (
                <div key={key} className={chipClass}>
                  {inner}
                </div>
              )
            }
            return external ? (
              <a
                key={key}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Open artifact"
                className={cn(chipClass, "transition-colors hover:bg-muted focus-visible:bg-muted")}
              >
                {inner}
              </a>
            ) : (
              <Link
                key={key}
                href={href}
                aria-label="Open artifact"
                className={cn(chipClass, "transition-colors hover:bg-muted focus-visible:bg-muted")}
              >
                {inner}
              </Link>
            )
          })}
        </div>
      ) : null}

All identifiers used above (ArrowUpRight, ArrowRight, artifactIcon, cn, Link,
FileReferenceChip) are already imported in the merged file. `Button` is still
used elsewhere in the file, so leave its import alone.

STEP 4 — everything else: accept the automatic merge. Take v0's apps/web
marketing changes and your own backend/docs/scripts/supabase/e2e changes as-is.

STEP 5 — verify before merging to main or deploying.

  git status                       # zero remaining unmerged (U) entries
  git grep -n "FileReferenceChip" -- apps/web/components/gravitre/assistant/chat-execution-panel.tsx
  pnpm -C apps/web exec tsc --noEmit

IMPORTANT type-check baseline: apps/web has exactly 7 PRE-EXISTING error TS2339s
in components/gravitre/assistant/file-reference-chip.tsx ('title'/'metadata' on
'HostedFileRef | ChatArtifact'). They exist on main alone, before any merge, and
the verified merge adds none. 7 is the expected result — do not fix them here. An
8th error, or any error in another file, means the merge went wrong.

Then run the "Pre-deploy verification" section of
docs/delivery/marketing-frontend-merge-plan-2026-08-04.md.

If anything contradicts the assumptions above — different conflict set, extra
type errors, a non-21 extension file count — STOP and report it instead of
forcing the merge through. These SHAs drift as commits land.
````

## Carried-forward open item

`apps/web/lib/marketing-copy.ts` claims "60+ templates" and "6 department packs"
directly above a marketplace grid rendering **10 assets / 4 packs**. Left
unchanged because the true catalog size is not derivable from the code. If the
counts describe the full catalog rather than the visible sample, the copy and
the grid should be reconciled so they do not contradict each other on screen.
