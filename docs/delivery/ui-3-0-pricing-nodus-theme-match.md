# UI 3.0 — Pricing page Nodus theme match

**Date:** 2026-09-07  
**Status:** Shipping

## What

`/pricing` rebuilt to Notus/Nodus pricing chrome (badge, monthly/yearly Scale toggle, 3-column divide rails, check feature lists, comparison matrix, FAQ accordion).

## Data honesty

**(a)** Explicitly requested Nodus theme match.  
Plan names, prices, descriptions, and feature lists remain **authorized Gravitre** data from `@/lib/pricing-page-data` / `PLAN_CATALOG` (Node / Control / Command).  
Template Growth/Scale/Enterprise demo dollars stay quarantined in `nodus-constants/pricing.tsx`.

## Files

- `components/marketing/nodus/pricing.tsx` — restored UI, Gravitre tiers
- `components/marketing/nodus/pricing-table.tsx` — restored matrix, Gravitre rows
- `app/(marketing)/pricing/page.tsx` — full page on Nodus rails
- FAQ accordion restyled to divide list
