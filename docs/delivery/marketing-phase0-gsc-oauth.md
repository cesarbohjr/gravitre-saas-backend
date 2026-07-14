# Marketing Pack (#6) — Phase 0: GSC OAuth findings

**Date:** 2026-07-14  
**Status:** Findings only — no GSC connection code written yet.  
**Question:** Can the existing OAuth connection flow be reused for Google Search Console?

## Verdict: **B — Reuse with small deltas**

| Option | Meaning | Applies? |
|--------|---------|----------|
| A | Reuse as-is (catalog/scope config only) | No — GSC is absent from the codebase |
| **B** | **Same Google OAuth flow; add vendor + scope + GCP + site picker** | **Yes** |
| C | New OAuth protocol / separate client app | No |

OAuth plumbing does **not** need a new flow. GSC fits the existing **unified Google vendor OAuth** path used by GA4, Calendar, Gmail, Drive, Docs, Sheets.

## Existing OAuth (what Marketing inherits)

- **Shared Google Cloud OAuth client** (`GOOGLE_OAUTH_CLIENT_ID` / `SECRET`) — one Gravitre app for all Google products (`docs/integration/GOOGLE_OAUTH.md`).
- **Unified vendor module:** `backend/app/connectors/google_vendor_oauth.py`
  - `GOOGLE_OAUTH_VENDORS` today: `google_analytics`, `google_calendar`, `gmail`, `google_drive`, `google_docs`, `google_sheets`
  - Per-vendor scopes in `_VENDOR_SCOPES`
  - Authorize: `access_type=offline`, `prompt=consent`, `include_granted_scopes=true`
- **Routes:** `backend/app/routers/connector_oauth.py` start + callback
- **Tokens:** encrypted `oauth_tokens` secret; refresh via `ensure_google_vendor_session` / `refresh_google_vendor_tokens_if_needed`
- **UI:** connectors page → `authType=oauth` → start → Google consent → callback → `/connectors?oauth=success…`
- **GA4 precedent for post-connect selection:** property picker / `selectProperty=1` when auto-link fails — GSC will need the same pattern for **site URL** selection (`searchAnalytics.query` requires `siteUrl`)

## GSC today

- **Zero** `search_console` / `webmasters` / `google_search_console` connector code, actions, or allowed-types.
- Phase 0 vision already flagged: *"Google Search Console | No (GA4 exists) | OAuth TBD | NEW for Marketing"*

## OAuth-specific deltas (small, required before connect works)

1. Add `google_search_console` to `GOOGLE_OAUTH_VENDORS`, aliases, and `_VENDOR_SCOPES`:
   - Scope: `https://www.googleapis.com/auth/webmasters.readonly` (read path only; full `webmasters` not needed for Marketing v1)
2. GCP: enable **Search Console API**; add scope to consent screen; register redirect  
   `…/api/connectors/oauth/google_search_console/callback` (same client, new redirect URI — same pattern as existing Google products)
3. Frontend: `connectors.ts` type + `SHIPPED_OAUTH_CONNECTOR_TYPES` / `OAUTH_VENDOR_KEYS`
4. DB: connector type allowed-types migration (same as other Google types)
5. Site selection UX after connect (mirror GA4 property linking) — `pending_site` / `site_url` in connector config

**Separate from GA4:** connecting GA4 does **not** grant GSC. GSC is a new connector row + fresh consent for `webmasters.readonly`.

**Not required:** new OAuth app, PKCE variant, or non-Google auth framework.

## Beyond OAuth (build after findings accepted)

API client + tools (`sites.list`, `searchAnalytics.query`), action catalog, PackSignalDefinition registration, PackKpiPanel, notifications/`result_url` 1:1 — same shared plumbing as packs 1–5.

## Secondary (pack constraints — not blocking OAuth decision)

| Item | Finding |
|------|---------|
| SEMrush | Catalog + UI `apiKey` / BYO; **no** live executor yet — apply Apollo-style BYO labeling when wired |
| Ahrefs | **Not in repo** — if shipped, add as BYO with same labeling pattern |
| Signals | `PackSignalDefinition` + `register_signal()` only — no new signal mechanism |
| KPI UX | Reuse `PackKpiPanel` + `/kpis` (CS / Prospecting template) |
| PII (prelim) | GSC Search Analytics can expose **query strings** that may include emails/PII-like tokens in rare cases — treat as **low but non-zero**; flag in governance before storing raw queries broadly. Campaign/traffic aggregates generally low risk. Confirm at build time; do not assume zero. |

## GCP console — human action (blocked until confirmed)

**Cursor cannot and will not do this.** Connection code stays blocked until a human with console access confirms the three changes are live.

| Step | Where |
|------|--------|
| 1. Enable **Search Console API** | Google Cloud → APIs & Services → Library |
| 2. Add scope `https://www.googleapis.com/auth/webmasters.readonly` | OAuth consent screen → Scopes |
| 3. Register redirect URI | Credentials → Gravitre OAuth client → Authorized redirect URIs |

**Redirect URI (production):**
```
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_search_console/callback
```
(Also register the app-domain rewrite form if that is how other Google callbacks are listed — same pattern as GA4/Drive in `docs/integration/GOOGLE_OAUTH.md`.)

### Who has access?

- **Cursor / agent:** no Google Cloud Console access.
- **Repo docs:** do **not** name a second GCP admin. Platform admin / governance owner is Cesar (`cesar.bohorquez.jr@gmail.com` in migrations); OAuth setup is documented as CLI (`npm run google:configure` / `google:fill-env` / `google:railway`) against the project that already hosts the six Google redirects.
- **Practical recovery:** open Railway → read `GOOGLE_OAUTH_CLIENT_ID` → in [console.cloud.google.com](https://console.cloud.google.com) find that OAuth 2.0 Client ID under APIs & Services → Credentials → apply the three steps above.
- If Cesar’s Google account cannot see that project, ownership must be recovered (billing account / org IAM / whoever originally created “Gravitre OAuth”) before Marketing OAuth can be tested.

**Confirm back in chat when the three steps are done** — only then does Verdict B unlock connection-code work.

### GCP confirm (2026-07-14)

Human confirmed: Search Console API enabled, `webmasters.readonly` on consent screen, redirect URI registered on existing Gravitre OAuth client. Verdict B unlocked for connection code.

## Stop-line — GSC query strings (STA-312 pattern, preemptively)

**Locked 2026-07-14 (Cesar):**

| Data | KG / Organizational Memory | Pack signal pipeline |
|------|----------------------------|----------------------|
| **Raw search query strings** (row-level `searchAnalytics.query` dimensions that include the query text) | **STOP** — no writes without governance sign-off (same bar as Crunchbase/PDL contact-level) | May use in-session / connector cache for workflows; do **not** persist into Memory/KG |
| **Aggregates / rollups** (clicks, impressions, position by URL/page; totals without query text) | Allowed under normal pack ingestion | Flow normally through `PackSignalDefinition` |

Governance owner: Cesar Bohorquez Jr. (STA-312 sole owner). This gate is intentional and preempts “rarely PII-adjacent” query strings (names in vanity searches, etc.).

## Verdict B acceptance gate

- [x] Verdict B accepted **contingent on** GCP human confirm + stop-line recorded (this doc + master program)
- [ ] GCP console steps 1–3 confirmed live by human
- [ ] Then proceed to GSC OAuth vendor entry + callback + site-picker (connection code)
