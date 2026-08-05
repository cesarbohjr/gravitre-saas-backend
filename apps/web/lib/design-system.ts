/**
 * Canonical type / radius / motion scale for the core app surfaces.
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

/** Text roles, largest to smallest. */
export const TYPE = {
  /** The single <h1> on a page. */
  pageTitle: "text-2xl font-semibold tracking-tight text-foreground md:text-3xl",
  /** Supporting sentence under a page title. */
  pageLead: "text-sm text-pretty text-muted-foreground",
  /** Section heading inside a page (<h2>). */
  sectionTitle: "text-lg font-semibold tracking-tight text-foreground",
  /** Card / list-item heading (<h3>). */
  cardTitle: "text-sm font-semibold leading-tight tracking-tight text-foreground",
  /**
   * Small caps label above a title or over a group of controls.
   * One tracking value everywhere — this was the worst offender.
   */
  eyebrow: "text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground",
  /** Caps label under a metric. Same tracking as eyebrow, lighter weight. */
  metricLabel: "text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground",
  /** Large number in a stat card. */
  metricValue: "text-2xl font-semibold tabular-nums text-foreground",
  /** Default body copy. */
  body: "text-sm leading-relaxed text-foreground",
  /** De-emphasised body copy. */
  bodyMuted: "text-sm leading-relaxed text-muted-foreground",
  /** Row meta, timestamps, counts. */
  meta: "text-xs text-muted-foreground",
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
 * Shared motion timings. Durations stay short enough to feel like feedback
 * rather than animation; every consumer must still honour `useReducedMotion()`.
 */
export const MOTION = {
  /** Hover / press feedback. */
  fast: 0.15,
  /** Enter + exit transitions. */
  base: 0.22,
  /** Staggered list reveals. */
  stagger: 0.04,
  /** Sliding indicators (tab pills, segmented controls). */
  spring: { type: "spring" as const, stiffness: 400, damping: 32 },
} as const

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
