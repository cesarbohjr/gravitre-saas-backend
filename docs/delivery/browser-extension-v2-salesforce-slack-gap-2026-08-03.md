# Extension v2 — Salesforce / Slack marketing gap (STEP 0)

Date: 2026-08-03

## Verdict

**Salesforce Lightning/Force and Slack web (`app.slack.com`) were listed on the live marketing page ahead of v2’s own gating standard.**

They do **not** have enrich → approved write → Outcomes proof on those surfaces.

## Evidence reviewed

| Claim | Status |
|-------|--------|
| v2 live smoke | `careers_about` only — run `4ec4829a-…` / tip-verify `75279569-…` |
| Salesforce surface enrich+write+Outcomes | **NOT RUN** — no artifact |
| Slack surface enrich+write+Outcomes | **NOT RUN** — no artifact |
| Tip org connectors (2026-08-03) | `salesforce` / `slack` **not connected** (`False` / `False`); connected includes apollo, hubspot, … |

## Correction shipped

Public copy no longer presents Salesforce / Slack as live-supported surfaces:

- `/features/extension` — moved to **Coming soon**
- Setup guide + FAQ — same honesty

Code may still allowlist those hosts for future proof; marketing must not claim them until a real Outcomes entry exists per surface.

## Re-open criteria

Connect Salesforce and/or Slack on a tip org → real enrich + approved catalog write from that surface → Outcomes `source=browser_extension` → then move from Coming soon to Supported and update this note.
