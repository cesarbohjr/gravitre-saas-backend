# Gravitre Brand Alignment Spec (Option B — Inspired)

**Goal**  
Align Gravitre's UI brand (colors, typography, spacing, component feel) to the same *discipline* as PromptWatch—clean, airy, grid-forward, minimal SaaS—while keeping a touch more Gravitre personality (slightly bolder accent moments, clearer systemization).

**Tech stack alignment (authoritative for implementation)**
- **Frontend:** React via **Next.js App Router**
- **Styling:** Tailwind CSS
- **Component layer:** shadcn/ui + Radix primitives (where used)
- **Theming:** CSS variables (HSL or RGB), `data-theme`/class-based switching

This spec is written to be **Cursor-friendly**: it defines **non-negotiables**, **allowed changes**, and **exact implementation rules** so Cursor doesn't invent patterns or partially implement "nice-to-haves."

---

## 1) Brand principles (what "Aligned" looks like)

1. **Whitespace-first UI**: generous padding, low visual noise, minimal decoration.
2. **Subtle structure**: light borders, faint section backgrounds, restrained shadows.
3. **Typography does the heavy lifting**: clear hierarchy, consistent sizes, minimal font variety.
4. **One primary action style**: a single recognizable CTA treatment.
5. **Data UI stays calm**: analytics look analytical (not neon).

---

## 2) Typography system (React implementation)

### 2.1 Typeface policy
- **Primary font (all UI):** Inter
- **No new fonts** introduced in product UI.

**Implementation rules**
- Next.js: set Inter via `next/font/google` (or a single self-hosted font) and bind to a CSS variable.
- Tailwind: `fontFamily.sans = ['var(--font-sans)', ...]`

**Cursor rule:** do not apply font families per-component; only via base layout (`<html>`/`<body>`).

### 2.2 Type scale (product)
Use a tight, predictable scale (no random values):
- H1: 40/48, 600
- H2: 32/40, 600
- H3: 24/32, 600
- H4: 20/28, 600
- Body: 16/24, 400
- Small: 14/20, 400
- Micro (labels): 12/16, 500

**Implementation rules**
- Define Tailwind text utilities via existing classes (e.g., `text-4xl`, `text-3xl`) or add named utilities using `@layer utilities`.
- Use `leading-*` and `tracking-*` consistently.

**Cursor rule:** no new font sizes outside this scale unless the scale is updated here first.

---

## 3) Color system (tokens → CSS vars → Tailwind → components)

### 3.1 Directional change (PromptWatch-inspired)
To align Gravitre without losing identity:
- Your existing lime/mint family becomes **Highlight/Positive** (not the main CTA).
- Introduce an **Action Blue** as the **Primary CTA** (buttons, links, focus rings).

This prevents "highlighter UI" while preserving Gravitre personality.

### 3.2 Token model (source of truth)
**Single source of truth:** design tokens JSON (light + dark) → compiled into CSS variables.

**Required semantic roles (minimum set)**
- `--bg`, `--surface`, `--surface-2`
- `--border`, `--border-strong`
- `--text`, `--text-muted`
- `--action`, `--action-hover`, `--action-pressed`, `--focus`
- `--highlight` (maps to existing lime)
- `--success`, `--warning`, `--danger`

**Cursor rule:** no hardcoded hex in React components. All colors must come from semantic CSS variables.

### 3.3 Tailwind mapping
Use Tailwind's CSS variable strategy (recommended for shadcn/ui):
- `colors.background = 'hsl(var(--bg))'`
- `colors.foreground = 'hsl(var(--text))'`
- `colors.primary = 'hsl(var(--action))'`
- `colors.primaryForeground = 'hsl(var(--action-foreground))'` (define as needed)
- `colors.muted = 'hsl(var(--surface-2))'`
- `colors.border = 'hsl(var(--border))'`

**Cursor rule:** don't create parallel color systems (e.g., mixing `primary-300` tokens directly in components). Components consume *semantic* Tailwind colors.

### 3.4 Light/Dark theming
- Use class or attribute switching: `html[data-theme='dark']` (or `.dark`).
- Only the variable values change between modes.
- Component code does not branch on theme.

---

## 4) Radius, borders, shadows (React component rules)

### 4.1 Radius policy
Approved set:
- `radius-sm`: 10px
- `radius-md`: 12px
- `radius-lg`: 16px
- `radius-xl`: 20px (cards/modals only)

**Implementation rules**
- Map to Tailwind: `rounded-[10px]` etc **or** define via `--radius` and use shadcn conventions.
- Prefer shadcn default: `--radius` + `rounded-lg` etc.

**Cursor rule:** components may only use approved radii.

### 4.2 Border policy
- Borders are 1px.
- Border color is neutral and subtle.

### 4.3 Shadow policy
- Default surfaces: border-only (no shadow)
- Overlays (modal/popover): `shadow-sm` or `shadow-md` only
- Avoid heavy shadows for standard cards

**Cursor rule:** do not add new custom box-shadow values in components; define shadows in tokens/utilities.

---

## 5) Layout & UI composition (Next.js / React)

### 5.1 Page structure defaults
- 12-col grid desktop (Tailwind grid utilities)
- Standard gutters: 24–32px
- Section rhythm: 48–80px vertical spacing

### 5.2 Cards
Cards are flat and bordered.
- Default card: `bg-surface border border-border rounded-lg`
- Highlight card: subtle tinted fill using `--highlight` at low alpha (implemented as a dedicated semantic var like `--highlight-surface`)

### 5.3 Buttons (shadcn/ui)
- Primary button = **Action Blue** (`primary`)
- Secondary = neutral outline
- Tertiary = ghost/text

**Implementation rules**
- Prefer shadcn `Button` variants; adjust tokens/vars so variants render correctly.
- Do not create "new" button variants unless added here.

---

## 6) Cursor execution rules (React edition)

### 6.1 What Cursor may change
- Token files (light/dark) and their build output (CSS variables)
- Tailwind config mapping to semantic vars
- Global styles (e.g., `globals.css`) that define theme variables
- Component styling **only to replace hardcoded values with semantic tokens**

### 6.2 What Cursor must NOT do
- Add product features, pages, flows, agents, or business logic
- Introduce new UI libraries
- Introduce new fonts
- Refactor unrelated code

### 6.3 Stop conditions (Cursor must halt and ask)
Cursor must stop if:
- A semantic role is missing (e.g., action hover state)
- A component needs a new variant not described here
- Theme switching mechanism is inconsistent with existing app patterns

Pause message template:

> "I can proceed once the theme mechanism and semantic token roles are confirmed (existing pattern vs new). Which approach should I follow?"

---

## 7) Implementation order (do this or don't do it)

1) **Tokens:** add Action Blue scale and semantic roles for light/dark.
2) **CSS variables:** define `--bg`, `--surface`, `--text`, `--action`, etc for both themes.
3) **Tailwind mapping:** connect semantic vars to Tailwind colors.
4) **Core components:** Button, Input, Select, Card, Modal, Tabs.
5) **Screens:** migrate page-by-page only after components are stable.

**Cursor rule:** never start at step 5.

---

## 8) Acceptance criteria

- UI reads as calm, airy SaaS.
- CTAs are consistently Action Blue.
- Lime/mint reads as highlight/positive, not primary CTA.
- Inter-only for new UI.
- Zero hardcoded hex in React components.
- No new features were created.

---

## 9) Cursor prompt template (copy/paste)

> **Task:** Implement Gravitre Brand Alignment Spec (Option B — Inspired) for the React/Next.js frontend.
> 
> **Scope:** Update tokens → CSS variables → Tailwind mapping → adjust existing React components to consume semantic tokens.
> 
> **Non-goals:** No new pages. No new features. No logic refactors. No new libraries. No new fonts.
> 
> **Stop if blocked:** missing semantic roles, mismatch with existing theme mechanism, or need for new component variants.
> 
> **Order:** (1) tokens, (2) css vars, (3) tailwind mapping, (4) core components, (5) pages.
