# 18 — Design-selection reviewability evidence

**Date:** 2026-09-23  
**Branch:** `feat/gravitre-3.0-plus-frontend`  
**Package commits:** `c5d2d5bd` · `e0690459` (+ this evidence commit)  
**Worktree:** `.cursor-tmp/wt-3.0-plus-frontend`  
**Server:** `http://127.0.0.1:3010` (webpack Next · `apps/web`)

## Working selection-index URL

**http://127.0.0.1:3010/dev/ai-workspace-preview?s=selection**

Also: `http://localhost:3010/dev/ai-workspace-preview?s=selection`

## Diagnosis (what was wrong)

| Symptom | Cause | Fix / outcome |
|---------|-------|----------------|
| Early “next not found” | Incomplete worktree install | `pnpm install` in worktree |
| Turbopack panic | Junction of `node_modules` → main tree | No junction; `next dev --port 3010 --webpack` |
| First request timeout | Cold compile of harness route | Wait for first compile; subsequent routes ~200–400ms |
| Missing env warnings | No local `.env` for Supabase/FastAPI | Harmless for fixture harness |
| Playwright auto-shots earlier | Browsers missing in sandbox | Cursor browser MCP screenshots of live harness |

## Route render proof (HTTP 200 + browser)

All required Cesar routes returned **200** after warm compile (2026-09-23, curl via PowerShell, max 120s):

| Query | Status | ~ms |
|-------|--------|-----|
| `?s=selection` | 200 | 410 |
| `?s=page-intro&scene=compare` | 200 | 358 |
| `?s=window-manager&scene=docked` | 200 | 225 |
| `?s=window-manager&scene=compact` | 200 | 198 |
| `?s=intelligence-journey&scene=field-primary` | 200 | 258 |
| `?s=workflow-rf` | 200 | 287 |
| `?s=workflow-gen` | 200 | 198 |
| `?s=ai-workspace&scene=split` | 200 | 299 |
| `?s=model-studio&scene=standard` | 200 | 246 |
| `?s=model-studio&scene=advanced` | 200 | 317 |
| `?s=dashboard` | 200 | 196 |
| `?s=agent-workspace` | 200 | 181 |
| `?s=workflow-rf&scene=live` | 200 | 324 |
| `?s=dashboard&scene=ops-board` | 200 | 245 |
| `?s=agent-workspace&scene=workbench` | 200 | 227 |

Browser MCP loaded interactive selection index with full A–G decision cards (problem / options / structure / preserved / interaction / responsive / tradeoffs / dependencies / Cesar chooses) and working deep links.

## Screenshot evidence (live harness — not concept art)

Stored under `docs/design/3.0-plus/selection-shots/`:

| File | Content |
|------|---------|
| `00-selection-index.png` | Enriched Cesar review index |
| `A-page-intro-compare.png` | Page-intro side-by-side |
| `A-page-intro-operating-mobile.png` | Compact / operating |
| `B-window-manager-docked.png` | WM docked (proposed default) |
| `B-window-manager-compact.png` | WM compact |
| `C-intelligence-field-primary.png` | Intelligence Field-primary |
| `D-workflow-rf-design.png` | Option B RF design |
| `D-workflow-gen-preview.png` | AI → workflow preview |
| `E-ai-workspace-split.png` | Shared AI split composition |
| `F-model-studio-standard.png` | Model Studio standard |
| `F-model-studio-advanced.png` | Model Studio advanced fields |
| `G-dashboard-attention-first.png` | §40 Dashboard attention-first |
| `G-agent-roster-detail.png` | §40 Agent roster→detail |

## How Cesar reviews

```bash
cd .cursor-tmp/wt-3.0-plus-frontend/apps/web
pnpm install   # once
node ./node_modules/next/dist/bin/next dev --port 3010 --webpack
```

1. Open **http://127.0.0.1:3010/dev/ai-workspace-preview?s=selection**
2. Use each A–G card’s links; compare structural options
3. Offline backup: `docs/design/3.0-plus/selection-shots/`
4. Record decisions in checklist on index / `17-design-selection-package.md`

## Cesar decisions (reserved — not agent-chosen)

- [ ] **A** — Intro map by family (Operating / Expert / Empty / Immersive)
- [ ] **B** — WM default mode (proposed: docked)
- [ ] **C** — Intelligence Field primacy + which of 3 concepts
- [ ] **D** — RF cutover **deferred** until preservation review (`14-option-b-preservation-evidence.md`)
- [ ] **E** — AI workspace composition direction (runtime stays core)
- [ ] **F** — Model Studio Standard/Advanced progressive disclosure
- [ ] **§40** — Optional Dashboard + Agent structural picks

## Core-agent / production protection confirmation

No edits this session to: `ai-workspace.tsx`, chat-execution-panel, ai-work-canvas, gravitre-command-os, chat API/SSE, production Workflow Builder, backend execution, governance.

Changed only: harness `design-selection-index.tsx` + `docs/design/3.0-plus/**` (evidence + shots).

Option B RF remains isolated visual prototype; gaps still documented (Meson apply, multi-handles, council, version restore, live runsApi).

## Remaining Phase 6/7 blockers

- Phase 7 authenticated journey proof: **NOT RUN** (harness ≠ production)
- RF Option B gaps unchanged — working prototype does **not** authorize cutover
- Cold first-compile latency on fresh server (environment, not product defect)
- No merge / deploy of this branch to production
