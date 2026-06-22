# Marketplace audit — skipped items (Lane C)

Items below remain **open in Linear** for tracking but were **skipped** in the M1–M4 code pass (superseded, deferred, or covered elsewhere). Do not close Linear issues without product sign-off.

Source: `docs/integration/marketplace-audit-linear-ids.json` (`skipped` array).

**M2 complete.** **M3 complete.** **M4 complete.** STA-250 ✅ paid checkout; STA-251 ✅ creator revenue share transfers; STA-252 ✅ partner registry ↔ connector_config; STA-253 ✅ hours saved ROI dashboard.

**M5 complete.** STA-255 ✅ publisher revenue analytics; STA-256 ✅ paid asset pricing UI; STA-257 ✅ publisher payout sync on billing.

**M1 doc polish complete.** STA-227 ✅ dual-marketplace convergence documented in `docs/integration/agent-role-marketplace.md` (§ Dual marketplace architecture).

**Next queue:** Close superseded pre-audit Linear epics (STA-180–222) or pick net-new marketplace work outside the audit.

---

## Skipped — M1 (STA-227 – STA-239)

| Ref | Linear | Title | Skip reason |
|-----|--------|-------|-------------|
| MKT-AUDIT-ARCH-1 | STA-227 | Document dual-marketplace convergence | ✅ Federation decision + scope matrix in `agent-role-marketplace.md` § Dual marketplace architecture |
| MKT-AUDIT-4.6 | STA-228 | business_outcome, use_case columns | ✅ Migration + browse/detail/create UI + seed backfill |
| MKT-AUDIT-4.5 | STA-229 | Expand catalog 27 → 50 | ✅ **Done** — prod `total=51`; close in Linear |
| MKT-AUDIT-5.4 | STA-230 | Fix internal visibility in browse | ✅ Browse filters + smoke `visibility_*` steps + Internal badge |
| MKT-AUDIT-5.5 | STA-231 | department_pack / knowledge_pack install tests | ✅ Unit + router install coverage |
| MKT-AUDIT-5.6 | STA-232 | LIMIT_EXCEEDED on install | ✅ Install sheet + `plan_limit_exceeded` toast |
| MKT-AUDIT-6.2 | STA-233 | Facet filters | ✅ **Done** — unified catalog sidebar + URL sync |
| MKT-AUDIT-6.3 | STA-234 | `/marketplace/assets/[slug]` | ✅ **OG metadata + opengraph image** |
| MKT-AUDIT-6.4 | STA-235 | Analytics dashboard UI | ✅ Publisher revenue + org adoption link |
| MKT-AUDIT-6.5 | STA-236 | Reviews and saves UI | ✅ Saved list + catalog save buttons |
| MKT-AUDIT-6.6 | STA-237 | Remove legacy role-pack client | Redirect to unified catalog ✅ |
| MKT-AUDIT-DOC-1 | STA-238 | Update V0_BACKEND_SYNC branch ref | ✅ `docs/integration/V0_BACKEND_SYNC.md` |
| MKT-AUDIT-QA-1 | STA-239 | E2E marketplace smoke in CI | ✅ `.github/workflows/marketplace-production-smoke.yml` |

---

## Skipped — M2 (STA-240 – STA-246)

| Ref | Linear | Title | Skip reason |
|-----|--------|-------|-------------|
| MKT-AUDIT-9.1 | STA-240 | Asset CRUD API | ✅ POST/PATCH/DELETE routes + create draft UI |
| MKT-AUDIT-9.2 | STA-241 | Internal publish workflow | ✅ Submit/approve/reject + org-admin queue |
| MKT-AUDIT-9.3 | STA-242 | Admin approval queue UI | ✅ `/marketplace/platform-admin` + hub pending counts |
| MKT-AUDIT-9.4 | STA-243 | Version snapshot on publish | ✅ Approve snapshots + org-admin version history/rollback |
| MKT-AUDIT-8.1 | STA-244 | Uninstall flow | ✅ Asset detail + installed pages |
| MKT-AUDIT-10.2 | STA-245 | Per-asset adoption events | ✅ Table + agent/workflow hooks + analytics dashboard |
| MKT-AUDIT-6.7 | STA-246 | Org marketplace tab | ✅ `/marketplace/org` + hub counts |

---

## Skipped — M3–M4 (STA-247 – STA-253)

| Ref | Linear | Title | Milestone |
|-----|--------|-------|-----------|
| MKT-AUDIT-11.1 | STA-247 | Creator publisher onboarding | ✅ Onboard API + `/marketplace/publisher` + public submit from org-admin |
| MKT-AUDIT-11.2 | STA-248 | Gravitre review queue | ✅ Queue API + platform-admin UI + cross-org review preview |
| MKT-AUDIT-11.3 | STA-249 | Featured / verified flags | ✅ Platform curation UI + home featured rail + catalog badges |
| MKT-AUDIT-12.1 | STA-250 | Paid install + Stripe checkout | ✅ Entitlement gate + checkout + install UI + webhook fulfillment |
| MKT-AUDIT-12.2 | STA-251 | Creator revenue share transfers | ✅ Ledger + 80/20 split + Connect transfers + sync UI |
| MKT-AUDIT-13.1 | STA-252 | Partner registry ↔ connector_config | ✅ Upsert on publish + federated browse + platform link/sync routes |
| MKT-AUDIT-13.2 | STA-253 | Hours saved ROI dashboard | ✅ `/analytics/roi` API + `/marketplace/analytics/roi` dashboard |

---

## Skipped — M5 (STA-255 – STA-257)

| Ref | Linear | Title | Milestone |
|-----|--------|-------|-----------|
| MKT-AUDIT-14.1 | STA-255 | Publisher revenue analytics dashboard | ✅ Combined earnings API + `/marketplace/publisher/analytics` dashboard |
| MKT-AUDIT-14.2 | STA-256 | Paid asset pricing in org/platform admin UI | ✅ Org + platform pricing editors, org pricing route, create draft pricing |
| MKT-AUDIT-14.3 | STA-257 | Publisher payout sync UI on marketplace billing | ✅ Transfer hero, sync results, pending badges on `/marketplace/billing` |

---

## Promote to active work

The **STA-223–257 marketplace audit** is complete in code and Linear. Remaining open items in the Gravitre Marketplace project are **superseded pre-audit epics** (STA-180–222) — close or cancel after spot-checking against shipped audit work.

Optional net-new work (no open audit issue):

1. Cancel/close legacy epics STA-180–222 in Linear
2. Full connector merge (future — see STA-227 doc § Future convergence)

Linear project: [Gravitre Marketplace](https://linear.app/staqbot/project/gravitre-marketplace)
