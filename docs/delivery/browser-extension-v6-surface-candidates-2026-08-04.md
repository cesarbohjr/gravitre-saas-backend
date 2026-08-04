# Extension v6 — surface candidates (usage-signal mine)

Date: 2026-08-04  
Source: `docs/delivery/browser-extension-v6-usage-signals.json`  
Script: `scripts/mine-extension-usage-signals.py`  
Gate: `docs/delivery/browser-extension-v6-gate-2026-08-03.md`

## Mine summary

| Field | Value |
|-------|-------|
| Rows | 24 |
| Scope | tip org `cbbf993b-…` (24) + global scan (0 additional) |
| Noise | 24 |
| Catalog backlog hosts | 0 |
| Possible DOM-forcing hosts | **0** |

## Classification

### possible_dom_forcing

**None.** No non-allowlisted production host remains after noise filters.

### catalog_backlog

**None** in this mine. (If HubSpot/Apollo/etc. product hosts appear later, they stay catalog — not v6.)

### noise (all current rows)

| Host | Why noise |
|------|-----------|
| `www.linkedin.com` | Tip smoke paths `/in/v5-parity-edge-brave` |
| `example.com` | `v5-parity` / `not-allowlisted` smoke |
| `www.acme-example.com` | v2 careers fixture |
| `outside-crm.example` | `v2_tip` fixture (`.example` TLD) |

## Verdict

**GATE REMAINS CLOSED.**

Zero named surfaces force agentic DOM. Closing the roadmap at v5 remains the correct outcome until:

1. Real `extension.usage_signal` hosts appear that have **no** governed API and a documented multi-step form need, **or**
2. An operator explicitly names such a surface.

This report does **not** authorize DOM automation code.

## Security review (commissioned)

[STA-340 — Extension v6 agentic DOM security review (gated)](https://linear.app/staqbot/issue/STA-340/extension-v6-agentic-dom-security-review-gated)

Backlog. Blocks v6 code. Not sign-off.

## Human pick (required before any v6 build)

Reply with one host/UI from a future mine (or a named operator surface). Until then: no agentic DOM implementation.
