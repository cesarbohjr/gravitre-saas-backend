# Enterprise Admin UI — v0 Design Prompt

Use this prompt in [v0.dev](https://v0.dev) as a **senior frontend developer** brief. Backend APIs and a functional baseline already exist at `/settings/enterprise`; your job is to elevate layout, visual hierarchy, and UX polish while preserving data contracts.

---

## Role

You are a senior frontend engineer designing the **Gravitre Enterprise Admin** experience — white-label branding, data residency, workforce analytics, cost attribution, and SIEM export. The product is an enterprise AI operations console (dark-first, professional, not playful).

## Stack constraints

- **Next.js App Router**, React 19, TypeScript
- **Tailwind CSS v4** + shadcn/ui components already in repo
- **SWR** for data fetching via `enterpriseApi` (`apps/web/lib/api.ts`)
- **Existing routes:** `/settings/enterprise` (admin), app shell applies branding via `EnterpriseBrandingProvider`
- Do not invent new API shapes; consume existing endpoints below

## API contracts (do not change)

| Endpoint | Purpose |
|----------|---------|
| `GET/PUT /api/enterprise/data-region` | `{ region: 'us'\|'eu', storagePrefix }` |
| `GET/PUT /api/enterprise/branding` | logoUrl, primaryColor, customDomain, customDomainVerified, hidePoweredBy, emailFromName |
| `GET /api/enterprise/branding/domain-instructions` | CNAME + TXT DNS records |
| `POST /api/enterprise/branding/verify-domain` | `{ verified, method, checks }` |
| `GET /api/enterprise/workforce-analytics` | tasksCompleted, tasksFailed, tasksRunning, handoffs, toolSuccessRate, approvalWaitEvents, slaBreaches |
| `GET /api/enterprise/cost-attribution` | totalCostUsd, byAgent, byDepartment, byWorkflow |
| `GET/PUT /api/enterprise/siem` | enabled, endpoint, hasSecret (secret never returned) |
| `POST /api/enterprise/siem/test` | test delivery |

## Pages to redesign

### 1. Enterprise Settings hub (`/settings/enterprise`)

Replace the current tab strip with a **premium admin layout**:

- **Left sub-nav** (desktop) / **segmented control** (mobile): Region · Branding · Workforce · Cost · SIEM
- **Page header**: title, one-line description, breadcrumb back to `/settings`
- **Admin gate**: non-admins see read-only analytics with a subtle lock callout

**Region tab**
- Card with US/EU map or region badges (not generic dropdown only)
- Show `storagePrefix` as copyable monospace chip
- Warning callout when changing region (connector tokens pinned to region)

**Branding tab**
- Split panel: **live preview** (mini app shell with logo + primary color) on the right
- Logo URL input + drag-drop upload placeholder (URL-only for now)
- Color picker synced to CSS `--primary`
- Custom domain section as a **stepper**: (1) Enter domain → (2) DNS records → (3) Verify → Verified badge
- DNS records as copy-to-clipboard rows (CNAME + TXT), not raw JSON
- Toggle: Hide “Powered by Gravitre”

**Workforce tab**
- KPI grid (6 metrics) with sparkline placeholders
- Empty state when all zeros
- Optional secondary table: recent handoff / approval events (placeholder rows OK)

**Cost tab**
- MTD total hero metric
- Bar chart or horizontal bars for top agents (use `byAgent` object)
- Department / workflow breakdown as compact list

**SIEM tab**
- Security-forward styling (shield motif, muted red accent for secrets)
- Endpoint URL + “rotate secret” pattern (blank keeps existing when `hasSecret`)
- Test delivery button with inline success/failure toast pattern

### 2. Dynamic branding in app shell

Enhance how branding applies globally (reference `apps/web/lib/enterprise-branding-context.tsx`):

- Sidebar logo respects `logoUrl`; fallback to Gravitre assets
- Primary color drives buttons, links, focus rings (`--primary`, `--ring`, `--sidebar-primary`)
- Footer “Powered by Gravitre” hidden when `hidePoweredBy`
- Optional: favicon/title suffix from `emailFromName` on enterprise routes only

## Visual direction

- **Brand base**: deep navy background `#0B0F14`, surfaces `#11161D`, electric blue accent (default) overridable by org primary color
- **Typography**: Geist — clear hierarchy (page title 20–24px semibold, section labels 11px uppercase tracking)
- **Density**: comfortable admin density — not marketing spaciousness
- **Motion**: subtle (150–200ms), no gratuitous animation
- **Accessibility**: WCAG AA contrast; focus visible on all controls; labels on every input

## UX requirements

- Optimistic save states with inline “Saved” confirmation
- Destructive actions (region change) require confirm dialog
- DNS verification: show **actionable errors** from `checks.cname` / `checks.txt` when verify fails
- Mobile: stack preview below form; sticky save bar on long forms
- Loading skeletons per tab, not full-page spinner

## Out of scope for v0

- Actual file upload to storage (logo remains URL)
- Vercel custom domain provisioning (DNS verify only)
- Email template editor

## Deliverables

1. React components for `/settings/enterprise` (can split into `components/enterprise/*`)
2. Updated `EnterpriseBrandingProvider` integration if preview needs shared state
3. shadcn components only (`Card`, `Tabs`, `Badge`, `Alert`, `Dialog`, `Button`, `Input`, `Separator`)
4. No backend changes

## Reference files in repo

- `apps/web/app/settings/enterprise/page.tsx` — current baseline
- `apps/web/lib/enterprise-branding-context.tsx` — branding CSS vars
- `apps/web/components/gravitre/app-shell.tsx` — shell + powered-by footer
- `apps/web/components/gravitre/sidebar.tsx` — logo slot

---

**Prompt shortcut for v0 chat:**

> Design a premium Enterprise Admin settings page for Gravitre (Next.js + shadcn + Tailwind v4). Tabs: Data Region, Branding with live preview + DNS verification stepper, Workforce KPIs, Cost attribution chart, SIEM config. Dark navy enterprise aesthetic. Use the API contracts above. Improve layout/UX over the existing `/settings/enterprise` baseline; include app shell branding preview.
