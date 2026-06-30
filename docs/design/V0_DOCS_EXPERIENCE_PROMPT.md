# v0 prompt — Documentation experience (MDX site polish + visuals)

Paste into [v0.dev](https://v0.dev) on a branch synced from `main` after commit `942b9dc7` (MDX docs platform). **Frontend design + marketing/docs UI only** — do not change MDX content files, loaders, or API routes unless wiring new presentational components.

---

## What's already shipped (do not rebuild)

### Public docs (`apps/web`)

| Piece | Path | Notes |
|-------|------|--------|
| MDX loader | `apps/web/lib/docs/load-docs.ts` | Reads `content/docs/public/**/*.mdx`, frontmatter, nav sections |
| Doc types | `apps/web/lib/docs/types.ts` | `audience`, `depth`, `tier`, `status`, prev/next |
| MDX components | `apps/web/lib/docs/mdx-components.tsx`, `components/docs/mdx-client.tsx` | Headings, links, `Callout`, `CodeBlock` (copy) |
| Doc page | `app/(marketing)/docs/[...slug]/page.tsx` | Hero + article + prev/next + footer CTA |
| Docs landing | `app/(marketing)/docs/page.tsx` | 8 quick links, featured guides, browse-by-topic, API card |
| OpenAPI | `app/(marketing)/docs/api/openapi.json/route.ts` | Redacted spec |
| Swagger UI | `app/(marketing)/docs/api/swagger/page.tsx` | Basic embed |
| Redirects | `apps/web/next.config.mjs` | Legacy `/docs/architecture` → platform overview |
| Content | `apps/web/content/docs/public/` | **63 MDX pages** — concepts, how-tos, API, integrations, FAQ |

### Internal docs (`apps/internal-docs/`)

- Password gate (`INTERNAL_DOCS_PASSWORD`), loads `docs/internal/**/*.md`
- Port 3001, `npm run dev:internal-docs`

### Naming reference

- `docs/design/NAMING_GLOSSARY.md` — use **docs names** in all UI copy (Multi-Agent Run, AI Models, Partner Connections, Runs not Tasks, etc.)

---

## Design problem

Content is comprehensive; **presentation is still “engineering default”**:

- Light zinc/emerald marketing shell with **no persistent docs sidebar** or in-page TOC
- MDX supports only `Callout` + `CodeBlock` — no steps, tabs, cards, screenshots, or diagrams
- Quick links use generic Lucide icons — no Gravitre doc illustration system
- **Zero product screenshots** in guides (Operator, Federation, Enterprise tabs, Runs timeline)
- FAQ is a long MDX page — not scannable accordion/search
- Swagger page is unstyled embed
- No blog/changelog/article template for future content marketing
- Docs visual language **diverges** from product (docs = white marketing; app = dark navy console)

**Goal:** Make `/docs` feel like Stripe/Linear/Vercel-quality documentation — trustworthy, scannable, visually anchored to the real product — without rewriting 63 MDX files by hand (components + layout first; MDX adoption second).

---

## Brand baseline

### Marketing / docs shell (public `/docs`)

- **Background:** white / zinc-50 sections (keep light-first for long-form reading)
- **Accent:** emerald-600/700 links and badges (existing)
- **Typography:** Geist or system sans; monospace for code
- **Tone:** Clear operator docs — not splashy SaaS marketing
- **Density:** Comfortable line length (`max-w-4xl` article, optional wider for diagrams)

### Product app (for screenshots & frames)

- **Surfaces:** `#0B0F14` bg, `#11161D` cards, org `--primary`
- **Reference:** `apps/web/components/gravitre/sidebar.tsx`, `AppShell`, Enterprise Federation page
- Screenshots should use **real UI** or high-fidelity mock frames that match dark console

### Motion

- Framer Motion on doc hero only (existing `doc-page-motion.tsx`) — subtle fade/slide
- Respect `prefers-reduced-motion`
- No parallax or heavy animation in article body

---

## Your task — design deliverables

Implement in **`apps/web`** under `(marketing)/docs` and `components/docs/`. Prefer **composable MDX components** over one-off page CSS.

---

### 1. Docs chrome — layout upgrade

**Routes:** `/docs`, `/docs/[...slug]`

Add a **three-zone layout**:

```
[ Marketing header — existing site nav ]
[ Sidebar nav | Article (+ sticky TOC) | Optional "On this page" rail ]
[ Footer — support + API links ]
```

**Sidebar (left, desktop ≥1024px):**

- Collapsible sections from `getDocsNavSections()` (Core Concepts, How-to Guides, API Reference, Integrations, FAQ, Billing)
- Active slug highlight
- Mobile: drawer triggered by "Menu" in doc header

**In-page TOC (right rail or below title on md):**

- Auto-generate from `h2`/`h3` in rendered MDX (client component with IntersectionObserver)
- Sticky within viewport; highlight current section

**Doc header enhancements:**

- Breadcrumb: Docs → Category → Title
- Badges: category, read time, **plan tier** (`tier: control|enterprise|all` from frontmatter)
- Optional "Edit on GitHub" link pattern (placeholder href ok)

**Do not** break `generateStaticParams` or MDX RSC compilation.

---

### 2. MDX component library (extend `mdx-components.tsx`)

Add styled components docs authors can use in MDX (register in `mdxComponents` export):

| Component | Purpose |
|-----------|---------|
| `<Steps>` / `<Step>` | Numbered setup flows (Quickstart, Connectors) |
| `<Tabs>` / `<Tab>` | API examples (curl / fetch / response) |
| `<Card>` / `<CardGrid>` | Feature summaries, plan comparison |
| `<Screenshot>` | Framed product screenshot with caption + optional annotation hotspots |
| `<ScreenshotPlaceholder>` | Gray frame + route label until real PNG exists |
| `<Diagram>` | ASCII/mermaid-friendly container with legend |
| `<PlanBadge>` | Node / Control / Command / Enterprise |
| `<TierCallout>` | "Requires Control plan" with link to billing doc |
| `<VendorLogo>` | HubSpot, Salesforce, etc. (SVG or img) |
| `<FAQItem>` | Question + answer block (for FAQ page refactor) |
| `<CompareTable>` | Docs name vs UI route (Partner Connections vs Federation) |

**Callout variants:** info (zinc), warning (amber), tip (emerald), danger (rose) — keep existing emerald default for backward compatibility.

**CodeBlock:** Add language label chip, line numbers optional, "Copy" + "Copied" (existing).

---

### 3. Product screenshot system

Create **screenshot frame component** and a **shot list** of PNGs to capture (or mock at 1440×900, 2x retina):

| Asset ID | Route | Used in docs |
|----------|-------|--------------|
| `docs-shot-operator` | `/operator` | AI Operator, Quickstart |
| `docs-shot-assistant` | `/assistant` | Assistant guide |
| `docs-shot-workflows-builder` | `/workflows/[id]/builder` | Workflows |
| `docs-shot-runs` | `/runs` | Runs, Approvals |
| `docs-shot-connectors` | `/connectors` | Connectors + integration pages |
| `docs-shot-marketplace` | `/marketplace` | Marketplace |
| `docs-shot-federation` | `/settings/federation` | Partner Connections |
| `docs-shot-enterprise-cs` | `/settings/enterprise?tab=cs` | Enterprise integration health |
| `docs-shot-enterprise-siem` | `/settings/enterprise?tab=siem` | Security log export |
| `docs-shot-settings` | `/settings` | Settings guide |
| `docs-shot-metrics` | `/metrics` | Metrics |
| `docs-shot-swagger` | `/docs/api/swagger` | API quickstart |

**Frame styling:**

- Dark app chrome mock window (traffic dots optional)
- Subtle shadow, rounded-xl, caption below in zinc-500
- Optional numbered **callout pins** (1, 2, 3) linking to bullet list

Store assets under `apps/web/public/docs/screenshots/` (WebP preferred).

Until real captures exist, use `ScreenshotPlaceholder` with route name — but **design the frame** so swapping PNG is one prop change.

---

### 4. Illustration & icon system (docs-only)

Design a **cohesive mini design system** for docs (SVG, 24–48px and hero 120–160px):

**Category icons** (replace generic Lucide on landing quick links):

- Quickstart, AI Operator, Assistant, Workflows, Connectors, Runs, Marketplace, API

**Concept illustrations** (optional hero art per section):

- WORK (Operator, Assistant, Search)
- BUILD (Workflows, Connectors, Marketplace, Meson)
- ACTIVITY (Runs, Schedules, Approvals)
- INSIGHTS (Metrics, History)
- ADMIN (Settings, Enterprise, Partner Connections)

Style: flat vector, emerald + zinc + single accent hue per category; match Gravitre logo geometry; **not** generic 3D blobs.

**Trust / B2B graphic** for Partner Connections doc:

- Two org nodes, mutual consent gate, read-only grant arrow — reuse visual language from `TrustBoundaryVisual` in Federation UI

Export to `apps/web/public/docs/icons/` and `apps/web/public/docs/illustrations/`.

---

### 5. Docs landing page (`/docs`) polish

Enhance existing sections — **do not remove** dynamic nav from loader.

**Hero:**

- Subtle grid or dot pattern (light, like Linear docs)
- Primary CTA: Start here → Quickstart
- Secondary: API explorer, Core concepts
- Optional hero illustration (operator + workflow abstract)

**Popular guides grid (8 cards):**

- Custom icon per card
- Hover: border-emerald-300 + slight lift
- Show read time

**Featured how-to grid:**

- Thumbnail = screenshot frame or category illustration
- Category pill + title + read time

**Browse by topic:**

- Two-column on lg; max 6 links per column with "Show all" if >8

**API reference card:**

- Terminal mock with `curl gravitre.app/api/workflows`
- Buttons: Swagger, openapi.json, quickstart

**Social proof row (optional):**

- "Trusted by operations teams" — placeholder logos grayed (no fake customers)

---

### 6. FAQ experience (`/docs/faq`)

Transform FAQ from wall-of-text MDX into:

- **Search/filter** input (client-side filter on question text)
- **Accordion** by section (Getting started, Marketplace, Partner Connections, Enterprise, API…)
- Deep-linkable `#anchor` per question
- "Still stuck?" card → Contact + link to relevant guide

Keep MDX source — render via `FAQItem` components or parse headings in page wrapper.

---

### 7. Integration pages polish (`/docs/integrations/*`)

10 vendor pages exist. Add consistent template:

- Vendor logo header row
- "Production-ready" badge
- Prerequisites checklist card
- Steps component for OAuth/API key flow
- Screenshot: connector detail or OAuth screen (placeholder ok)
- Related links: Connectors guide, Workflows, API

---

### 8. API docs (`/docs/api/*` + Swagger)

**Swagger page:**

- Full-width layout with Gravitre header
- Sidebar: tag groups (workflows, runs, federation, enterprise, operator)
- Styled Swagger UI overrides (emerald accents, zinc borders) — inject CSS module or link tag

**API index + quickstart:**

- Endpoint cards with method badges (GET/POST)
- Base URL callout: `https://gravitre.app/api`
- Auth diagram: Settings → API Keys → Bearer header

---

### 9. Blog / articles / changelog template (future-ready)

Scaffold **one reusable template** (can be empty state):

- Route: `/docs/blog` or `/blog` (pick one; prefer `/blog` for marketing separation)
- Article layout: hero image, author, date, tags, reading time, MDX body
- Changelog variant: version badge, "What changed" + links to docs anchors

Design only — minimal placeholder listing page ok.

---

### 10. Open Graph & SEO visuals

- Default OG image template: Gravitre logo + doc title on zinc/emerald gradient (`1200×630`)
- Per-category OG variants (API, Integrations, Guides) — 3 templates sufficient

---

## Copy & terminology rules (strict)

Use glossary names in **all UI chrome** (sidebar labels, badges, screenshot captions):

| Show in docs UI | Do not show |
|-----------------|-------------|
| Multi-Agent Run | Agent Swarm |
| AI Models | Model Registry |
| Workflows | Automations |
| Connectors | Apps |
| Runs | Tasks (for execution history) |
| Partner Connections | Federation (in customer-facing chrome; route `/settings/federation` ok in technical tables) |
| Integration health | Command Center (Enterprise doc context) |
| Security log export | SIEM Export |
| Meson | (keep brand) |

When showing **UI screenshots** where app still says "Federation", add caption: *UI may show "Federation"; docs use Partner Connections.*

---

## Constraints

- **No backend changes**
- **Do not delete or rewrite** the 63 MDX files in this pass — add components + layout; optionally update **Quickstart** and **Partner Connections** MDX as reference implementations only (2 files max)
- **No new npm dependencies** unless essential (e.g. `rehype-slug` for heading anchors) — justify in handoff
- Keep `next-mdx-remote/rsc` pipeline working
- TypeScript strict; `pnpm exec tsc --noEmit` in `apps/web`
- Internal docs app (`apps/internal-docs`) — optional dark theme alignment; lower priority than public `/docs`

---

## File targets (suggested)

```
apps/web/components/docs/
  docs-layout.tsx          # sidebar + toc shell
  docs-sidebar.tsx
  docs-toc.tsx
  docs-breadcrumb.tsx
  screenshot-frame.tsx
  mdx-steps.tsx
  mdx-tabs.tsx
  mdx-cards.tsx
  mdx-faq.tsx
  plan-badge.tsx
  vendor-logo.tsx

apps/web/app/(marketing)/docs/
  layout.tsx               # wrap all docs routes with DocsLayout
  [...slug]/page.tsx       # integrate layout + toc
  page.tsx                 # landing polish
  faq/page.tsx             # optional wrapper if needed
  api/swagger/page.tsx     # styled swagger

apps/web/public/docs/
  screenshots/
  icons/
  illustrations/
  og/
```

---

## Manual test checklist (v0 handoff)

1. `/docs` — landing renders; all 8 quick links work; featured guides match slugs
2. `/docs/getting-started/quickstart` — sidebar active state; TOC tracks scroll; Steps component renders
3. `/docs/guides/how-to/partner-connections` — screenshot frame + trust diagram visible
4. `/docs/integrations/hubspot` — vendor header template
5. `/docs/faq` — accordion + search filter works
6. `/docs/api/swagger` — readable in light mode; not broken embed
7. Mobile 375px — sidebar drawer; no horizontal scroll on code blocks
8. `pnpm exec tsc --noEmit` passes in `apps/web`

---

## Priority order (if time-boxed)

1. Docs layout + sidebar + TOC (**P0**)
2. MDX Steps, Tabs, Screenshot frame, Callout variants (**P0**)
3. Landing page visual polish + custom icons (**P1**)
4. FAQ accordion + search (**P1**)
5. Integration page template (**P1**)
6. Swagger styling (**P2**)
7. Screenshot PNG capture or realistic mocks for top 6 routes (**P2**)
8. Blog/changelog scaffold + OG templates (**P3**)

---

## Sync note

After v0 edits, merge via existing workflow (`docs/integration/V0_BACKEND_SYNC.md`). Cursor wires any missing loader hooks; **do not** duplicate content authoring — design system + layout first, then incrementally adopt new MDX components in high-traffic pages (Quickstart, AI Operator, Workflows, Connectors, Partner Connections, Enterprise, FAQ).
