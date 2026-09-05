# Advanced Design — tranche 4 (2026-09-04)

**Program:** Canvas §J remaining STATUS surfaces after tranche 3 `c2a44acf`.

## Shipped

| Area | Change |
|------|--------|
| Workflows list | `workflow-card` status + node status dots → status CSS vars |
| Dialogue mode | Retokened `DialogueModeChip`; mounted in transcript (non-clarify last assistant) |
| Marketplace | Honest-gap / discovery warning → pending status tokens + RADIUS |
| Workflow risk | Failure alerts high, pre-run severity, intelligence-drawer medium/high |
| Meson | Confidence chrome + bar dots → STATUS / STATUS_DOT |
| GIBE packs | Knowledge fabric health tones → STATUS + RADIUS.panel |
| Intelligence helpers | `modelStatusChipClass` / `agentStatusBadgeClass` → STATUS |

## Verification

- `npx tsc --noEmit` / `check-chat-surface-drift` — run at commit
- Prod marketing spot-check: `https://gravitre.app/` loads (How-it-works steps present). Tranche 4 visuals land after Vercel picks up this commit.

## Residuals (not claiming §64 CLOSED)

1. **Design Mode / Cesar human visual review** — still required for HUMAN DESIGN REVIEW PASS
2. **Voice human functional verify** — outside this program
3. **subagent / mcp Agent Elements shell** — deferred (layout risk)
4. Decorative workflow node-type colors (source/agent/task rainbow) left as type language, not status

## Customer surfaces

No new prices/claims/badges/Enable toggles. **(a)** Approved visual augmentation. Model status chips only retoken existing API status strings (TRAINED/READY etc.) — do not invent new honesty claims.
