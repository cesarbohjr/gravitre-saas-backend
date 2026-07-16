# Phase 1 Batch 1 — GitHub (2026-07-16)

## Scope

Fourth connector in approved Batch 1 order (after Apollo → HubSpot → Slack).

| Item | Detail |
|------|--------|
| API version | GitHub REST `2022-11-28` — **no bump** |
| New actions | `github.pulls.create`, `github.actions.runs.list`, `github.issues.update` |
| Chat / ReAct / canvas | **Not granted** |

## Tip prerequisite

Smoke org `cbbf993b-…` currently has **no GitHub connector**. Connect GitHub (OAuth `repo` + `read:user`), set `owner`/`repo` on the connector, then re-run:

`python scripts/smoke-phase1-github-batch1-live.py`

Optional: `GITHUB_SMOKE_HEAD=<branch>` to tip `pulls.create` as a draft PR.

## Evidence

- Live tip: [`phase1-github-batch1-live.json`](./phase1-github-batch1-live.json)

## Governance

- Finance/HR live-activation **HOLD** — unchanged
- Chat access deferred until tip review

## Next

Salesforce (one connector per PR), same expansion bar.
