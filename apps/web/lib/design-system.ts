/**
 * Canonical type / radius / motion / semantic scale for Gravitre surfaces.
 *
 * UI 3.0 (2026-09-05): light-first Design System 3.0 · Hybrid A+B marketing
 * direction (A product stage + B living execution; C = GIBE sections).
 * SOT: docs/delivery/gravitre-design-system-3.0.md
 *
 * Why this file exists: an audit of the five main hub pages found the same role
 * expressed a different way on nearly every page — page titles as `text-xl`
 * (schedules), `text-lg sm:text-2xl font-bold` (assignments) and
 * `text-2xl md:text-3xl font-semibold` (marketplace); eyebrow labels using
 * `tracking-wide`, `tracking-wider` AND `tracking-[0.2em]`, two of them inside
 * the same file. Those are the same semantic element, so they must resolve to
 * one string.
 *
 * Rule: never hand-write these class strings in a page. Import the token, so a
 * change lands everywhere at once and pages cannot silently drift again.
 *
 * The marketplace/assets treatment is the agreed baseline.
 */

/** Text roles, largest to smallest (app / hub density). */
export const TYPE = {
  /** The single <h1> on a page — Nodus product scale (~20–24px), not marketing H1. */
  pageTitle:
    "font-sans text-xl font-semibold tracking-tight text-[color:var(--g-text-primary)] sm:text-2xl",
  /** Supporting sentence under a page title. */
  pageLead: "font-sans text-sm text-pretty text-[color:var(--g-text-muted)]",
  /** Section heading inside a page (<h2>). */
  sectionTitle:
    "font-sans text-base font-semibold tracking-tight text-[color:var(--g-text-primary)] sm:text-lg",
  /** Card / list-item heading (<h3>) / widget title. */
  cardTitle:
    "font-sans text-sm font-semibold leading-tight tracking-tight text-[color:var(--g-text-primary)]",
  /**
   * Small caps label above a title or over a group of controls.
   * One tracking value everywhere — this was the worst offender.
   */
  eyebrow:
    "font-sans text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--g-text-muted)]",
  /** Caps label under a metric. Same tracking as eyebrow, lighter weight. */
  metricLabel:
    "font-sans text-[10px] font-medium uppercase tracking-[0.14em] text-[color:var(--g-text-muted)]",
  /** Large number in a stat card. */
  metricValue:
    "font-sans text-2xl font-semibold tabular-nums text-[color:var(--g-text-primary)]",
  /** Default body copy. */
  body: "font-sans text-sm leading-relaxed text-[color:var(--g-text-primary)]",
  /** De-emphasised body copy. */
  bodyMuted: "font-sans text-sm leading-relaxed text-[color:var(--g-text-muted)]",
  /** Row meta, timestamps, counts. */
  meta: "font-sans text-xs text-[color:var(--g-text-muted)]",
  /** Table header labels (Nodus Product Image). */
  tableHead:
    "font-sans text-xs font-medium text-[color:var(--g-text-muted)]",
  /** Table cell primary values. */
  tableCell:
    "font-sans text-sm font-medium tabular-nums text-[color:var(--g-text-primary)]",
} as const

/**
 * Marketing / editorial type roles (UI 3.0 Phase 3+). Geist sans only —
 * Phase 0.5 mock serif is not production. Unused by live pages until Phase 3.
 */
export const TYPE_MARKETING = {
  display:
    "font-sans text-[length:var(--g-type-display)] font-semibold leading-[1.05] tracking-[var(--g-type-display-tracking)] text-[color:var(--g-text-primary)]",
  h1: "font-sans text-[length:var(--g-type-h1)] font-semibold leading-tight tracking-tight text-[color:var(--g-text-primary)]",
  h2: "font-sans text-[length:var(--g-type-h2)] font-semibold leading-snug tracking-tight text-[color:var(--g-text-primary)]",
  h3: "font-sans text-[length:var(--g-type-h3)] font-semibold tracking-tight text-[color:var(--g-text-primary)]",
  lead: "font-sans text-lg leading-relaxed text-[color:var(--g-text-secondary)] md:text-xl",
  body: "font-sans text-[length:var(--g-type-body)] leading-relaxed text-[color:var(--g-text-secondary)]",
  label:
    "font-sans text-[length:var(--g-type-label)] font-semibold uppercase tracking-[var(--g-type-label-tracking)] text-[color:var(--g-text-muted)]",
  caption: "font-sans text-[length:var(--g-type-caption)] text-[color:var(--g-text-muted)]",
} as const

/**
 * Semantic color roles → CSS custom properties (UI 3.0).
 * Prefer these over raw hex / Tailwind palette for brand-adjacent UI.
 */
export const SEMANTIC = {
  canvas: "var(--g-canvas)",
  graphite: "var(--g-text-primary)",
  intelligence: "var(--g-intelligence)",
  intelligenceSoft: "var(--g-intelligence-soft)",
  intelligenceSurface: "var(--g-intelligence-surface)",
  emerald: "var(--g-emerald)",
  emeraldSoft: "var(--g-emerald-soft)",
  emeraldSurface: "var(--g-emerald-surface)",
  signal: "var(--g-signal)",
  signalSoft: "var(--g-signal-soft)",
  signalSurface: "var(--g-signal-surface)",
  approval: "var(--g-approval)",
  approvalSoft: "var(--g-approval-soft)",
  approvalSurface: "var(--g-approval-surface)",
  danger: "var(--g-danger)",
  success: "var(--g-success)",
  warning: "var(--g-warning)",
} as const

/**
 * Radius roles. The audit found `rounded-lg`, `rounded-xl`, `rounded-2xl`,
 * `rounded-3xl` and `rounded-full` all used for surfaces of the same rank.
 *
 * The hierarchy is shape-by-role, and it splits "controls" in two:
 *
 *   - Click targets are pills: button, badge, chip, tab trigger.
 *   - Text fields are rounded rectangles: input, textarea, select trigger.
 *     A pill wastes horizontal padding and reads oddly at wide widths, so
 *     `field` is deliberately NOT `control`.
 *   - Containers step up with their size: tile -> card -> panel.
 *
 * These are enforced in the primitives (components/ui/button.tsx, badge.tsx,
 * tabs.tsx, input.tsx, textarea.tsx, select.tsx), so ordinary call sites should
 * pass no radius at all. Reach for these tokens only for a bespoke element that
 * isn't already a primitive — a hand-rolled anchor styled as a chip, say.
 *
 * Two traps that produced the original mix of pills and rectangles:
 *   1. A convention that relies on each page opting in will drift. Only 6 of
 *      ~175 files with buttons ever imported this file, so ~97% of the app kept
 *      the primitive's default shape. Shape belongs in the primitive.
 *   2. Never re-declare a radius in a `cva` size variant. cva appends variant
 *      classes after the base, so the variant silently wins — that is exactly
 *      how `sm`/`lg` buttons stayed square while `default` ones were pills.
 */
export const RADIUS = {
  /** Click targets: buttons, chips, badges, tab triggers. */
  control: "rounded-full",
  /** Text entry: input, textarea, select trigger. Intentionally not a pill. */
  field: "rounded-md",
  /** Cards and list rows. */
  card: "rounded-xl",
  /** Panels and toolbars that contain cards. */
  panel: "rounded-2xl",
  /** Small square affordances: icon tiles, avatars, swatches. */
  tile: "rounded-lg",
} as const

/**
 * Shared motion timings (UI 2.0 Phase 9 — single source for MOTION + animations.timing).
 * Durations stay short enough to feel like feedback rather than animation;
 * every consumer must still honour `useMotionPrefs()` / `useReducedMotion()`.
 *
 * Scale: micro 150 · ui/base 250 · major 400 · slow 600 (seconds for Framer).
 */
export const MOTION = {
  /** Hover / press / exit micro interactions (150ms). */
  micro: 0.15,
  /** Alias of micro — prefer `micro` in new code. */
  fast: 0.15,
  /** Standard UI enter/exit (250ms). */
  ui: 0.25,
  /** Alias of ui — existing hub consumers; keep in sync with `ui`. */
  base: 0.25,
  /** Major surface / route transitions (400ms). */
  major: 0.4,
  /** Emphasis / slow reveals (600ms). */
  slow: 0.6,
  /** Staggered list reveals. */
  stagger: 0.04,
  /** Sliding indicators (tab pills, segmented controls). */
  spring: { type: "spring" as const, stiffness: 400, damping: 32 },
} as const

/**
 * Motion concepts (UI 3.0 grammar). Labels only — intensity and reduced-motion
 * behaviour live in `animations.ts` / voice presentation / CSS `--g-motion-*`.
 *
 * Canonical: FLOW · PULSE · WAVE · TRACE · RESOLVE · TRANSFER · FOCUS.
 * `ORBIT` is legacy compat — do not use in new UI 3.0 work.
 */
export const MOTION_CONCEPT = {
  FLOW: "flow",
  PULSE: "pulse",
  WAVE: "wave",
  /** @deprecated UI 3.0 — prefer FLOW / TRACE / TRANSFER. Kept for existing callers. */
  ORBIT: "orbit",
  TRACE: "trace",
  RESOLVE: "resolve",
  TRANSFER: "transfer",
  FOCUS: "focus",
  /** Shared packet motif (Design Pass 2) — marketing Intelligence Field first. */
  SIGNAL: "signal",
} as const

/**
 * Semantic status chip classes — Nodus soft-pill highlights (soft fill + strong text).
 * Borderless pills match Product Image model tags / status accents.
 * Use for BO / approval / agent honesty chips — never invent TRAINED/live claims.
 */
export const STATUS = {
  pending:
    "border border-transparent bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]",
  approved:
    "border border-transparent bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
  rejected:
    "border border-transparent bg-destructive/10 text-destructive",
  running:
    "border border-transparent bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
  failed:
    "border border-transparent bg-destructive/10 text-destructive",
  verified:
    "border border-transparent bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
  estimate:
    "border border-transparent bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]",
  paused:
    "border border-transparent bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]",
  idle:
    "border border-transparent bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)]",
} as const

export type StatusTone = keyof typeof STATUS

/** Dot fill paired with STATUS chip tones (Nodus status column). */
export const STATUS_DOT: Record<StatusTone, string> = {
  pending: "bg-[color:var(--g-approval)]",
  approved: "bg-[color:var(--g-brand)]",
  rejected: "bg-destructive",
  running: "bg-[color:var(--g-brand)]",
  failed: "bg-destructive",
  verified: "bg-[color:var(--g-brand)]",
  estimate: "bg-[color:var(--g-approval)]",
  paused: "bg-[color:var(--g-approval)]",
  idle: "bg-[color:var(--g-text-muted)]",
}

/**
 * Soft highlight pills — use only for important status (Ready / Watch / Error).
 * Category labels (“Topic knowledge”, “Available”) stay quiet outline/neutral.
 */
export const HIGHLIGHT = {
  brand:
    "border border-transparent bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]",
  signal:
    "border border-transparent bg-[color:var(--g-signal-soft)] text-[color:var(--g-signal)]",
  intelligence:
    "border border-transparent bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]",
  warning:
    "border border-transparent bg-[color:var(--g-approval-soft)] text-[color:var(--g-approval-bright)]",
  danger: "border border-transparent bg-destructive/10 text-destructive",
  neutral:
    "border border-transparent bg-[color:var(--g-surface-2)] text-[color:var(--g-text-secondary)]",
} as const

export type HighlightTone = keyof typeof HIGHLIGHT

/** Shared geometry for highlight / status pills. */
export const CHIP = {
  base: "inline-flex w-fit max-w-full items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold",
  compact: "inline-flex w-fit max-w-full items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
  /** Status column: colored dot + graphite label (no fill). */
  plain: "inline-flex w-fit max-w-full items-center gap-1.5 text-sm font-medium text-[color:var(--g-text-primary)]",
} as const

/**
 * Map a raw API / UI status string onto a STATUS tone.
 * Unknown values fall back to `idle` (muted) — never invent "live/trained".
 */
export function resolveStatusTone(status: string): StatusTone {
  const key = status.trim().toLowerCase().replace(/[\s-]+/g, "_")
  const map: Record<string, StatusTone> = {
    pending: "pending",
    awaiting_approval: "pending",
    awaiting: "pending",
    queued: "pending",
    approved: "approved",
    approve: "approved",
    success: "approved",
    completed: "verified",
    verified: "verified",
    rejected: "rejected",
    reject: "rejected",
    denied: "rejected",
    failed: "failed",
    error: "failed",
    running: "running",
    in_progress: "running",
    processing: "running",
    active: "running",
    estimate: "estimate",
    estimated: "estimate",
    partial_success: "estimate",
    flagged_for_review: "pending",
    warning: "pending",
    idle: "idle",
    paused: "paused",
    draft: "idle",
    cancelled: "idle",
    canceled: "idle",
    muted: "idle",
  }
  return map[key] ?? "idle"
}

/**
 * Icon-only button sizing for app chrome (top bar, page toolbars).
 *
 * A 32px square holding a 16px glyph is comfortable with a mouse but sits under
 * the 44px touch-target guidance and reads as visually tiny on a phone — so the
 * larger step is the mobile default and desktop opts back down.
 */
export const TOUCH_ICON_BUTTON = "h-11 w-11 sm:h-8 sm:w-8 [&_svg]:size-5 sm:[&_svg]:size-4"

/** Canonical hover/focus transition for interactive surfaces. */
export const INTERACTION =
  "transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
