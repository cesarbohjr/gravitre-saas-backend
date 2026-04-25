# FE-00 — Frontend Foundation & Brand/Token Wiring

**Authority:** docs/brand/Gravitre_Brand_Alignment_Spec.md (non-negotiable).  
**Scope:** App shell, identity surface, token wiring only. No product features.

---

## Temporary Token Scaffolding

**design/tokens/*.json is not present in the repo.** Per MASTER_PHASED_MODULE_PLAN, minimal semantic CSS variables are defined in `app/styles/globals.css` and marked as **TEMPORARY**.

- **Replace when:** Figma exports (Light.tokens.json, Dark.tokens.json, Mode 1.tokens.json) are added under `design/tokens/`.
- **Do not invent** new values beyond Brand Spec ranges. Current values are placeholders for Action Blue (primary CTA), highlight (lime), and semantic roles.

---

## Brand Spec Compliance

- **Font:** Inter via `next/font/google`, bound to `--font-sans` (Brand Spec §2.1).
- **Primary CTA:** Action Blue via `--action`; Tailwind `primary` maps to it (§3.3).
- **Highlight:** Lime/positive via `--highlight`; not used as primary (§3.1).
- **Radii:** 10, 12, 16, 20px only (§4.1).
- **Theming:** `.dark` on `<html>` (§3.4); no component branching on theme.
- **No hardcoded hex** in components; all colors from semantic CSS variables.

---

## Identity Surface

- Calls `GET ${NEXT_PUBLIC_API_BASE}/api/auth/me` with Bearer token from Supabase session.
- **States:** loading, unauthenticated (no session or 401), authenticated with org_id, authenticated with org_id null (onboarding pending).
- **Onboarding pending:** Renders neutral “Onboarding pending — contact admin for org access.” No optimistic UI; no fake data.

---

## What FE-00 Does NOT Include

- RAG UI, workflows, operators
- Onboarding flows, role management
- Sign-in form (Supabase hosted or custom is out of scope)
- Sidebar, dashboards, feature pages
- New product routes beyond `/`
- Any deviation from Brand Spec
