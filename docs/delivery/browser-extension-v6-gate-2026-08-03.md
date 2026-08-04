# Browser extension v6 gate — close roadmap at v5

Date: 2026-08-03

## Gate criteria (required before any v6 code)

1. A specific, named surface with **no** governed API and a documented, real operator need for genuine multi-step form interaction there.
2. A dedicated security review for prompt-injection risk on DOM/agentic control (Anthropic’s publicly disclosed risk category for this class of capability).

## Finding

After v1–v5:

- Allowlisted surfaces (LinkedIn, Gmail, Outlook, Salesforce, Slack, careers/about) already route through governed catalog actions (`EXTENSION_ALLOWED_ACTIONS`) or typed workflows — no parallel DOM action system.
- Usage-signal capture (v2) records hosts outside the allowlist for prioritization; no signal yet names a surface that **requires** multi-step form automation because an API cannot exist.
- Building agentic DOM capability “to complete the numbered list” would violate the standing rule (catalog action if one exists; no parallel action system) and would expand prompt-injection attack surface without a named operator case.

## Decision

**Close the extension roadmap at v5.** Do not build v6 unless/until a named surface + operator need + security review are explicitly provided.

This is a complete, legitimate outcome.

## Marketing

Do **not** publish copy implying “full agentic” browser control. Docs and `/features/extension` state that catalog actions are used when they exist and that agentic DOM capability was deliberately not built.

## Surface mining (2026-08-04)

Path: mine `extension.usage_signal` → classify → commission security review → **no DOM code** until human surface pick.

| Item | Result |
|------|--------|
| Script | `scripts/mine-extension-usage-signals.py` |
| Rows | 24 (tip org; global scan added 0) |
| `possible_dom_forcing` | **0** (all rows smoke/fixture noise) |
| Candidates doc | `browser-extension-v6-surface-candidates-2026-08-04.md` |
| Security review issue | [STA-340](https://linear.app/staqbot/issue/STA-340/extension-v6-agentic-dom-security-review-gated) (Backlog; blocks v6 code; not sign-off) |

**Verdict unchanged:** gate remains closed. STA-340 commissions the review checklist; it does not authorize build.
