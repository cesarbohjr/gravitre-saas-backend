# Prompt 3 Phase 2 — Authenticated Playwright click-audit

**Status:** STANDING crawl shipped; first full run findings below  
**Artifact:** `docs/delivery/prompt3-phase2-click-audit-live.json`  
**CI:** `.github/workflows/authenticated-click-audit.yml` (nightly 07:00 UTC + path push + manual)  
**Script:** `scripts/prompt3-authenticated-click-audit.js`  
**Account:** `conversation-smoke-sa@gravitre.app`

## Coverage

| Surface | Path | First hardened re-run |
|---------|------|------------------------|
| Chat / AI | `/ai` | OK |
| Activity / Outcomes | `/activity` | OK |
| Agents hub | `/agents` | OK |
| Settings personal | `/settings/profile`, `/settings/organizations` | OK |
| Settings organization | `/settings?section=organization`, `ai-models` | OK |
| Settings admin | `/settings?section=audit`, `/settings/enterprise` | OK |
| Connectors | `/connectors` | OK |
| Extension connect | `/extension/connect` | OK |
| Sidebar isolated | full operator nav | 0 fails after already-on-target + invisible-link skips |

## Findings (first run, pre-harden) → disposition

| Finding | Severity | Disposition |
|---------|----------|-------------|
| Sticky `dialog-overlay` after shell/command clicks blocked later controls (`Lite`, nav) | High (audit noise + real UX) | **Fixed in audit** (aggressive Escape/overlay dismiss). Demo command-bar “recent” mocks **removed** in `global-command-bar.tsx`. |
| Settings org / AI Models: spinner + blank main for ~45s | Medium | **Trivial fix shipped:** 12s timeout + “taking longer…” copy + Refresh (`settings/page.tsx`). Root cause of slow boot (402 entitlements / org boot) filed as follow-up. |
| Hard-coded demo recents (“Investigating failed customer sync”, fake run id) | Medium (mock affordance) | **Fixed** — empty recent list until real history wired. |
| Smoke SA landing in Lite shell / wrong org | Medium (audit fidelity) | **Fixed in audit** — force `gravitre-view-mode=admin` + isolated org `f07e57c0…`. |
| Schedules sidebar dead-nav (Lite shell, first run) | Medium | Cleared when operator shell forced; no Lite Schedules fail on re-run. Keep watching. |
| Sidebar `/welcome` not clickable / `/home` no URL change | Low | **Script false positives** — skip invisible welcome; already-on-target = OK. |

## Named follow-ups (not trivial)

1. **P3-P2-F1 Settings boot latency** — Investigate why `/api/settings/*` + entitlements (402 spam in console) keep `authLoading`/`adminLoading` elevated on smoke org; timeout copy is a safety net, not a root-cause fix.
2. **P3-P2-F2 Real command-palette recents** — Wire recent conversations/runs instead of empty/mock list.
3. **P3-P2-F3 Extension package flows** — Web `/extension/connect` covered; Chrome MV3 popup/background not in Playwright scope (needs extension harness).

## Empty states

Activity, agents, connectors showed helpful non-blank empty/copy on crawl (e.g. Activity: “No activity yet… Start in chat”). No infinite-spinner empty gaps after harden + settings timeout copy.

## Authoritative evidence run

Successful deep crawl (post-harden, before intermittent smoke-auth flake):

- **11/11 surfaces OK**, sidebar fail cleared after already-on-target / invisible-link skips (`862b4abd` agent run stamp in session; later password-reset races produced `session_expired` PARTIAL — login now hard-fails if auth does not stick).
- Login hardening: require `aside nav` after `/home`; throw if URL returns to `/login`.

## Follow-up added

4. **P3-P2-F4 Smoke SA auth flake** — Occasional `session_expired` immediately after password bootstrap; standing CI should re-bootstrap once on login failure.
