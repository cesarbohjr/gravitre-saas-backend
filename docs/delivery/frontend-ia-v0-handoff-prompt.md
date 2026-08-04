# v0 visual handoff prompt (post–IA consolidation)

**Status:** Handoff ready (functional IA bar met). Visual work not started in-repo.  
**Prerequisite evidence:** [frontend-ia-consolidation-verify.md](./frontend-ia-consolidation-verify.md)

## How to use

1. Copy the entire **Paste into v0** fenced block below into v0 (or your design tool).
2. Optionally attach screenshots of production (or tip) pages: `/activity`, `/agents`, `/intelligence`, `/settings`, plus the admin sidebar.
3. Ask v0 to return comps for **shell + four hubs only** (desktop first; mobile as a second pass).
4. Do **not** ask v0 to invent new top-level nav or new product routes — IA routes are locked.

---

## Product context (one line)

Gravitre is an enterprise operator product: dense, calm admin UI for running agents, workflows, and governed outcomes — not a marketing site.

## Locked sidebar inventory (~14 primary; Getting Started optional)

Keep these destinations; do not add peers:

| Section | Items |
|---------|--------|
| WORK | Getting Started (setup only), Home, Chat, Agents, Assignments, Goals |
| BUILD | Marketplace, Workflows, Connectors, Sources |
| ACTIVITY | Activity, Schedules, Approvals |
| INSIGHTS | Intelligence |
| SETTINGS | Settings |

## Hub layout intent (preserve structure)

| Hub | Route | Internal structure |
|-----|-------|--------------------|
| **Activity** | `/activity` | Execution timeline feel; tabs **All** · **Failures** (predictive alerts) |
| **Agents** | `/agents` | In-hub tabs **Roster** · **Multi-agent** · **Training**; detail stays one profile shell |
| **Intelligence** | `/intelligence` | Section grid: operational health, business outcomes/ROI, learning/golden signals, models (built-in + registry), memory, predictive |
| **Settings** | `/settings` | Progressive disclosure: **Personal** · **Organization** · **Admin** (Enterprise, Federation, Environments, permissions, HITL, Audit) |

## Hard do-not list

- No new top-level sidebar items
- No resurrecting deleted peers as nav (Runs list, Outcomes, Metrics, Failure Alerts, Multi-Agent Run, Training, Agent intelligence, Enterprise, Federation, Environments as siblings)
- No inventing pages or renaming hubs away from Activity / Agents / Intelligence / Settings
- Preserve IA routes (`/activity`, `/agents`, `/intelligence`, `/settings` and existing deep-links)
- No new marketing chrome on app surfaces
- No purple-on-white / purple-indigo gradient dashboard look
- No warm cream + terracotta serif “AI template” look
- No broadsheet / dense newspaper layout
- Avoid glow stacks, emoji decoration, and pill-cluster clutter

## Visual direction

- Operator clarity and density first
- One clear hierarchy per hub: title → tab/section switcher → content
- Prefer existing product language (neutral surfaces, restrained accent) over novelty themes
- Desktop shell: left sidebar + main canvas; icon-rail collapsed state is allowed

---

## Paste into v0

```text
Redesign the Gravitre admin app shell and four consolidated hubs. Gravitre is an enterprise operator product — dense, calm UI for agents, workflows, and governed outcomes, not a marketing site.

LOCKED SIDEBAR (~14 primary items; do not add destinations):
WORK: Getting Started (optional/setup), Home, Chat, Agents, Assignments, Goals
BUILD: Marketplace, Workflows, Connectors, Sources
ACTIVITY: Activity, Schedules, Approvals
INSIGHTS: Intelligence
SETTINGS: Settings

FOUR HUBS ONLY (visual redesign; keep routes and structure):
1) Activity (/activity) — feel like an execution timeline. Tabs: All | Failures (predictive failure alerts). List + detail for completed work (BusinessOutcomes).
2) Agents (/agents) — in-hub tabs: Roster | Multi-agent | Training. One coherent detail profile; no second “intelligence agents” surface.
3) Intelligence (/intelligence) — section grid into: Operational health, Business outcomes/ROI, Learning & golden signals, Models (built-in + registry), Memory, Predictive.
4) Settings (/settings) — progressive disclosure tiers: Personal | Organization | Admin. Admin holds Enterprise, Federation, Environments, permissions, HITL config, Audit — not separate top-level nav.

HARD CONSTRAINTS:
- Visual redesign only. Do not invent new top-level nav or new product pages.
- Do not bring back retired peers as sidebar items (Runs list, Outcomes, Metrics, Failure Alerts, Multi-Agent Run, Training, Agent intelligence, Enterprise, Federation, Environments as siblings).
- Preserve hub names and routes: Activity, Agents, Intelligence, Settings.
- Operator density and clarity; no marketing chrome on app surfaces.
- Avoid clichés: purple-on-white / purple-indigo gradients; warm cream + terracotta serif; broadsheet newspaper layouts; glow stacks; emoji decoration; pill-cluster clutter.

DELIVERABLES:
- Desktop comps for: admin shell (sidebar + chrome), Activity, Agents, Intelligence, Settings.
- Show tab/section switchers and hierarchy clearly.
- Optional: collapsed icon-rail sidebar state.
- Mobile as a second pass only after desktop shell + four hubs.
```
