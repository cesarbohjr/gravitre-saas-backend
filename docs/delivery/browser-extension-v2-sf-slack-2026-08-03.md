# Extension v2 — Salesforce + Slack surface enhance (closed)

Date: 2026-08-03

## Scope

Complete v2 surface proof for Salesforce Lightning/Force and Slack web after STEP 0 honesty correction. CWS listing CTA remains setup-guide until store URL is wired (`NEXT_PUBLIC_CHROME_WEB_STORE_URL`).

## Code enhance

- `apps/extension/content/slack.js` — extract `slackUserId` + optional company
- `apps/extension/content/salesforce.js` — extract `salesforceRecordId`
- Apollo org search include `slack` surface when company/domain present
- Smoke: `scripts/live-extension-v2-sf-slack-smoke.py`

## Live proof — PASS

Artifact: `docs/delivery/browser-extension-v2-sf-slack-live.json`

| Surface | Enrich | Write | Outcomes | Notification |
|---------|--------|-------|----------|--------------|
| Salesforce | apollo.people.match + hubspot.contacts.search + apollo.organizations.search | `hubspot.lists.create` | [`a3919eea-…`](https://gravitre.app/outcomes/a3919eea-ce7a-4584-8361-0ecd8ccc00d6) `source=browser_extension` | `1bf59663-…` |
| Slack | same catalog path | `hubspot.lists.create` | [`41fb7a3e-…`](https://gravitre.app/outcomes/41fb7a3e-b092-4704-b6be-251c72e6b120) `source=browser_extension` | `fd248e66-…` |

Native `salesforce.leads.search` / `slack.users.info`: **NOT RUN** (connectors not connected on tip org). Surface gate met via page_url detect + catalog enrich/write.

## Marketing

`/features/extension` + docs/FAQ: Salesforce / Slack moved from Coming soon → Supported after this proof.
