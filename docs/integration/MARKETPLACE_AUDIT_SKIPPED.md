# Marketplace audit — skipped items (Lane C)

Items below remain **open in Linear** for tracking but were **skipped** in the M1–M4 code pass (superseded, deferred, or covered elsewhere). Do not close Linear issues without product sign-off.

Source: `docs/integration/marketplace-audit-linear-ids.json` (`skipped` array).

**Current focus for Lane C:** STA-239 ✅ CI workflow; STA-232 ✅ plan limit UX; STA-235 ✅ publisher asset type column.

---

## Skipped — M1 (STA-227 – STA-239)

| Ref | Linear | Title | Skip reason |
|-----|--------|-------|-------------|
| MKT-AUDIT-ARCH-1 | STA-227 | Document dual-marketplace convergence | Doc-only; covered in `V0_MARKETPLACE_UNIFIED_PROMPT.md` |
| MKT-AUDIT-4.6 | STA-228 | business_outcome, use_case columns | Deferred — not blocking unified catalog |
| MKT-AUDIT-4.5 | STA-229 | Expand catalog 27 → 50 | ✅ **Done** — prod `total=51`; close in Linear |
| MKT-AUDIT-5.4 | STA-230 | Fix internal visibility in browse | Backend shipped; verify in staging |
| MKT-AUDIT-5.5 | STA-231 | department_pack / knowledge_pack install tests | Test debt — backlog |
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
| MKT-AUDIT-9.1 | STA-240 | Asset CRUD API | M2 — partner submit flow partial |
| MKT-AUDIT-9.2 | STA-241 | Internal publish workflow | M2 |
| MKT-AUDIT-9.3 | STA-242 | Admin approval queue UI | ✅ `/marketplace/platform-admin` + hub pending counts |
| MKT-AUDIT-9.4 | STA-243 | Version snapshot on publish | M2 |
| MKT-AUDIT-8.1 | STA-244 | Uninstall flow | API exists; UI on asset detail |
| MKT-AUDIT-10.2 | STA-245 | Per-asset adoption events | M2 analytics |
| MKT-AUDIT-6.7 | STA-246 | Org marketplace tab | M2 |

---

## Skipped — M3–M4 (STA-247 – STA-253)

| Ref | Linear | Title | Milestone |
|-----|--------|-------|-----------|
| MKT-AUDIT-11.1 | STA-247 | Creator publisher onboarding | M3 |
| MKT-AUDIT-11.2 | STA-248 | Gravitre review queue | M3 |
| MKT-AUDIT-11.3 | STA-249 | Featured / verified flags | M3 |
| MKT-AUDIT-12.1 | STA-250 | Paid install + Stripe checkout | M4 |
| MKT-AUDIT-12.2 | STA-251 | Creator revenue share transfers | M4 |
| MKT-AUDIT-13.1 | STA-252 | Partner registry ↔ connector_config | M4 |
| MKT-AUDIT-13.2 | STA-253 | Hours saved ROI dashboard | M4 |

---

## Promote to active work

When picking up marketplace backlog again, prefer in order:

1. **STA-246** — Org marketplace tab (M2)
2. **STA-244** — Uninstall flow UI on asset detail
3. **STA-240** — Asset CRUD API polish (M2)

Linear project: [Gravitre Marketplace](https://linear.app/staqbot/project/gravitre-marketplace)
