# Phase 6 — v0 visual handoff (flagged-for-review + Cursor v0 style)

**Status:** Handoff ready only after functional Phase 6 tip-matched PASS.  
**Prerequisite:** [phase6-flagged-for-review-ui.md](./phase6-flagged-for-review-ui.md) + live JSON artifact.  
**Rule:** Visual redesign only. No DTO field renames, no status renames, no new parallel status system, no new top-level nav.

## How to use

1. Confirm functional PASS on tip (`/health` `git_sha` matches shipped commit).
2. Copy the entire **Paste into v0** block below into v0 (or Cursor design canvas).
3. Attach screenshots of tip/prod: Activity list+detail with a flagged row, chat BusinessOutcome card, extension overlay, Intelligence reports ROI grid.
4. Ask for desktop comps first; mobile second.
5. After any visual restyle lands in-repo: **re-run** `python scripts/verify-phase6-flagged-ui-live.py` and Activity filter smoke — mandatory regression gate.

## Locked product facts (do not invent)

| Surface | Route / host | Renderer |
|---------|--------------|----------|
| Activity | `/activity` | List + `BusinessOutcomeView` detail |
| Chat | `/ai` | Same `BusinessOutcomeView` (`density=chat`) |
| Run inspector | `/runs/[id]` | Same view (`density=timeline`) |
| Extension | content overlay | Compact DTO card (badge + finding + next actions) |
| Reports | `/intelligence/reports` | ROI cards with `measurement_status=` honesty |

### Four BusinessOutcome presentation states (already wired)

| State | When | Feel |
|-------|------|------|
| Verified | `verification.verified === true` | Confident success |
| Not verified / unproven | happened, no proof | Calm neutral |
| **Flagged for review** | `status === flagged_for_review` or `reviewState` | Calm concern + specific uncertainty |
| Failed | `status === failed` | Clear direct negative |

Flagged must **not** read as Failed, and must **not** read as Verified.

### Finding content (already in DTO — design must show it)

- `verification.checkFailed`: `batch_degeneracy` vs `follow_up_proof` (distinguishable)
- `verification.finding`: e.g. `6 of 6 records returned the same industry: 'cannot tell'`
- `verification.nextActions[]`: specific next steps
- Card section order stays: Evidence → Summary → Explanation → Verification → Timeline → Recommendations → …

## Hard do-not list

- No new top-level sidebar items or new product routes
- No inventing a fifth status vocabulary
- No purple-on-white / purple-indigo gradient look
- No warm cream + terracotta serif “AI template” look
- No broadsheet / dense newspaper layout
- No glow stacks, emoji decoration, or pill-cluster clutter
- No hiding the finding behind a generic “Something went wrong”
- No data-contract or behavior changes in the visual pass

## Visual direction

- Operator clarity; dense calm admin UI
- Flagged = warning token (amber/ochre from existing `--warning`), not destructive red
- Same typography, spacing, and component language as existing BusinessOutcome cards and hub shells
- Legible at full Activity page, inline chat card, extension overlay, and dashboard widget scales

---

## Paste into v0

```text
Redesign Gravitre’s honest assurance states for BusinessOutcome + Insights — visual only. Gravitre is an enterprise operator product: dense, calm UI for agents, workflows, and governed outcomes — not a marketing site.

LOCKED IA (do not add nav or pages):
WORK: Home, Chat, Agents, Assignments, Goals (+ Getting Started optional)
BUILD: Marketplace, Workflows, Connectors, Sources
ACTIVITY: Activity, Schedules, Approvals
INSIGHTS: Intelligence (+ /intelligence/reports)
SETTINGS: Settings

DATA CONTRACT (already shipped — render only, do not invent fields):
BusinessOutcome card sections: Evidence → Summary → Explanation → Verification → Timeline → Recommendations → Diff/Undo when present.
Four presentation states derived from DTO:
1) Verified — success green / confident
2) Not verified — calm neutral dashed
3) Flagged for review — NEW: calm concern using warning amber; distinct from Failed and from Verified
4) Failed — destructive red / clear negative

Flagged DTO fields to design for (must remain readable at every scale):
- Pill label: “Flagged for review”
- verification.checkFailed: batch_degeneracy | follow_up_proof (labels must stay distinguishable)
- verification.finding: concrete sentence, e.g. “6 of 6 records returned the same industry: 'cannot tell'”
- verification.nextActions: 2–3 specific operator steps (list)
- Activity list: filterable status “Flagged for review”; row must be visually distinguishable (warning rail / tint) so it is never buried among completed items
- Chat inline card + run inspector + browser extension compact overlay: same state language, same finding prominence

Insights / reports honesty (Phase 5, visual polish only):
- ROI / effectiveness cards that are not_configured or insufficient_data must look like weak/absent evidence — never like a confident KPI
- Match Module C TRAINED-vs-not-trained honesty pattern: calm disclosure, not alarmist failure chrome

SURFACES TO COMP (desktop first):
A) Activity hub — list with mixed verified / flagged / failed rows + detail pane showing a flagged card with finding + next actions open
B) Chat — inline flagged BusinessOutcome card on mesh background (solid card surface, left warning accent)
C) Extension overlay — compact flagged badge + finding + next actions + evidence links
D) Intelligence reports ROI grid — not_configured / insufficient_data treatment beside live_outcomes cards

HARD CONSTRAINTS:
- Visual redesign only. Zero API/DTO/behavior changes.
- Reuse existing component language (cards, pills, hub filter bar, StatusBadge warning variant).
- No purple gradients, no cream+terracotta serif template, no broadsheet, no glow/emoji clutter.
- Flagged ≠ Failed ≠ Verified — three different emotional reads.

DELIVERABLES:
1) Desktop comps for A–D
2) Mobile pass for Activity list+detail and chat card
3) Spec notes: spacing, token usage (--warning vs --destructive vs --success), and which elements stay collapsed by default on timeline density
```

## Post-v0 regression gate (mandatory)

After any visual PR/merge:

1. `python scripts/verify-phase6-flagged-ui-live.py` → `verdict=PASS` on tip
2. Activity: filter `flagged_for_review` shows the probe run; detail shows finding
3. Confirm chat / extension still render the same DTO fields (no missing finding)
