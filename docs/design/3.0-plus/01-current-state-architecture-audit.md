# 01 — Current-state architecture audit (Phase 0)

**Evidence date:** 2026-09-23  
**Sources:** repo inspection + Cesar screenshots of live product + inventory from parallel explore agents  
**Verdict:** Functional depth is real; **visual/product composition is still generic SaaS** and does not yet express Gravitre 3.0 Plus as one AI-native operating environment.

## What the screenshots prove (product reality)

| Surface | Observed | 3.0 Plus gap |
|---------|----------|--------------|
| Intelligence | Matrix lens primary (domain×lens table); Field secondary; Ask strip above | Signature Field Topology subordinated to spreadsheet density |
| Intelligence LEARNS spatial | Core + model satellites; caption-only | Spatial works but still “admin graph”, not adaptive work |
| Workflow builder | Custom node cards + empty Meson Suggests/Alerts/Tips | Dual AI entry (Meson vs Ask); empty copilot panel reads unfinished |
| Marketplace | Catalog list + Install rows | Premium discovery objects not yet; ops-list density OK |
| Workflows list | Cards + Table; copy leak “after the list, not instead of it” | Developer meta in customer chrome |
| Assignments | KPI cards + list; **“3500% confident”** | Honesty / formatting defect class |
| Agents | Roster Graph of department cards | Not relational ops graph; template grid |
| Goals | Empty state with generic page header | Acceptable empty; still page-template chrome |
| `/ai` | Bubble chat; duplicated user message in shot | Conversation exists; Command OS / work canvas not dominant |
| Dashboard | Stat cards + donut + monitor table | Classic SaaS dashboard; not intent-first |

## Architecture layers (as shipped)

1. **Shell:** `AppShell` + icon rail (`sidebar-nav-config.ts`) + `TopBar` — Nodus-derived light chrome.
2. **Intent layer:** One AI runtime (`ai-workspace.tsx`) with helper/float/expanded/fullscreen; Ask Gravitre summon; Meson as parallel affordance.
3. **Expert workspaces:** Workflows builder, Intelligence map/matrix, Agents, Connectors, Marketplace, Activity — mostly independent page templates.
4. **Design system:** Tailwind 4 + shadcn/Radix + Nodus product wrappers + Nucleo (partial) + Lucide/Phosphor still heavy.
5. **Data:** SWR → FastAPI; org via `x-org-id`; Intelligence page-context; chat SSE.

## Retain (do not rip out)

- Single AI runtime (not a second chat product)
- Nodus tokens / layout rhythm; emerald brand
- Canonical workflow persistence (`builder-persistence.ts` ↔ backend)
- Intelligence canonical graph / page-context contracts
- Governance surfaces (approvals, audit, write gates) as **truth**

## Structural defects (architecture, not paint)

| ID | Defect | Impact |
|----|--------|--------|
| A1 | No first-class **docked** Window Manager mode | Spec modes incomplete |
| A2 | Presentation modes ≠ shared Window Manager product | Mode changes risk state drift if redesigned carelessly |
| A3 | **Meson** and **Ask Gravitre** compete as AI entry | Splits intent layer |
| A4 | Workflow canvas is **custom**, React Flow only on Relationships | Spec prefers React Flow for ops graphs — migration needed, not install-and-replace |
| A5 | Page intro monoculture (`GravitrePageHeader` ~55–60 uses) | Screenshots all feel like the same SaaS template |
| A6 | Intelligence Matrix elevated over Field | Undermines approved I1 Field primary direction |
| A7 | Harness prototypes ahead of production composition | Risk of redesigning without shipping grammar |

## Honest constraints

- Master Word doc present on disk starts mid-spec (“Floating UI…”); Phase methodology (0–2) and stack refs recovered from extract + Cesar authorization Section 44 list.
- Functional 3.0-D owns artifact truth — frontend must render, not invent.
