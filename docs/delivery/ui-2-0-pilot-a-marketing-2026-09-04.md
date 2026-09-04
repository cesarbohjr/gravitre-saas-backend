# GRAVITRE UI 2.0 — Pilot A (Marketing hero) delivery

**Date:** 2026-09-04  
**Scope:** Home first viewport only + marketing chrome shell/CTA token share  
**Depends on:** Pilot E complete; Phase 7 tools

---

## Aceternity MCP (post-reload)

| Check | Result |
|-------|--------|
| Root `package.json` `"registries"."@aceternity"` | Added (monorepo MCP looks at workspace root) |
| `list_items_in_registries(['@aceternity'])` | **PASS** — 278 items |
| Pattern used in hero | Extracted beams motif → `HeroBrandBeams` (emerald/`--primary`/`--info` only — no purple Aceternity chrome) |

---

## What shipped

| Item | Change |
|------|--------|
| First viewport budget | Brand · one headline · one subhead · CTA group · ProductPreview |
| Removed from hero | Badge pill + `ProductTruthPills` cluster (OUT per brief) |
| Tokens | Zinc island → `background` / `foreground` / `primary` / `muted` / `border` / `card` |
| Motion | `useMotionPrefs()` on hero parallax, beams, product preview; reduced → static |
| Chrome share | Shell + Get Started CTAs use `bg-primary` (nav + mobile) |
| Copy | Unchanged (`MARKETING_COPY.hero`) |
| Claims | No new prices / TRAINED / Enable; preview keeps honesty metrics copy |

---

## Files

- `components/marketing/home/hero-parallax.tsx`
- `components/marketing/home/hero-brand-beams.tsx` (new)
- `components/marketing/home/product-preview.tsx`
- `components/marketing/marketing-chrome.tsx`
- `app/(marketing)/page.tsx` (page shell `bg-background`)
- root `package.json` (`@aceternity` registry for MCP)

---

## Verification

| Check | Result |
|-------|--------|
| Aceternity MCP list | PASS — 278 items |
| Invented customer surfaces | None added |
| Live browser screenshot desktop/mobile | **NOT RUN** this pass (code-complete; visual QA pending) |
| Reduced-motion | Implemented in code; live OS preference check **NOT RUN** |

Below-fold home sections remain zinc-heavy — out of Pilot A scope (later reskin).

---

## Customer-surface declaration

**(a)** No new prices, capability claims, badges, or Enable toggles.  
Existing honesty line in ProductPreview retained (“never a fabricated public %”).
