/**
 * Gravitre chat canvas background themes.
 *
 * Department icon-pattern tiles only — no gradient / mesh washes. Each theme is
 * a seamless PNG tile per app theme (light / dark), with the design-specified
 * 0.15 opacity pre-baked into the asset's alpha channel by
 * `scripts/bake-chat-pattern-alpha.mjs`. Baking rather than layering lets the
 * canvas render the tile as a plain `background-image` with
 * `background-attachment: local`, so it scrolls with the message list and never
 * sits on top of message content.
 *
 * CSS lives in globals.css keyed on `.ai-chat-canvas[data-chat-bg="<id>"]`.
 */

export type ChatBackgroundId = "marketing" | "sales" | "developers" | "operations" | "plain"

export type ChatBackgroundTheme = {
  id: ChatBackgroundId
  label: string
  description: string
  /**
   * Tile basenames under /patterns, or null for the no-pattern option. Used to
   * build the picker preview; the canvas itself is styled from globals.css.
   */
  tile: { light: string; dark: string } | null
}

/**
 * Retired gradient/mesh and pattern IDs → nearest current theme.
 * Read on load so an existing stored preference never renders as a blank canvas.
 */
const LEGACY_CHAT_BACKGROUND_IDS: Record<string, ChatBackgroundId> = {
  // Gradient mesh washes (removed).
  mesh: "marketing",
  signal: "developers",
  aurora: "developers",
  bloom: "marketing",
  dusk: "operations",
  tide: "sales",
  ember: "sales",
  // Earlier line/dot patterns (removed before the mesh washes).
  dotgrid: "marketing",
  grid: "developers",
  topo: "operations",
  diagonal: "developers",
  constellation: "operations",
  plus: "marketing",
  hex: "operations",
  lattice: "sales",
}

export const CHAT_BACKGROUND_THEMES: ChatBackgroundTheme[] = [
  {
    id: "marketing",
    label: "Marketing",
    description: "Megaphone, target, and growth-curve icons.",
    tile: { light: "gw-mkt-light.png", dark: "gw-mkt-dark.png" },
  },
  {
    id: "sales",
    label: "Sales",
    description: "Pipeline, handshake, and deal-flow icons.",
    tile: { light: "gw-sales-light.png", dark: "gw-sales-dark.png" },
  },
  {
    id: "developers",
    label: "Developers",
    description: "Terminal, branch, and build icons.",
    tile: { light: "gw-dev-light.png", dark: "gw-dev-dark.png" },
  },
  {
    id: "operations",
    label: "Operations",
    description: "Workflow, gear, and monitoring icons.",
    tile: { light: "gw-ops-light.png", dark: "gw-ops-dark.png" },
  },
  {
    id: "plain",
    label: "Plain",
    description: "Clean, distraction-free surface with no pattern.",
    tile: null,
  },
]

export const DEFAULT_CHAT_BACKGROUND: ChatBackgroundId = "marketing"

/** Tile size in px, matching the design handoff (desktop / mobile). */
export const CHAT_PATTERN_TILE_PX = { desktop: 234, mobile: 180 } as const

const VALID_IDS = new Set<string>(CHAT_BACKGROUND_THEMES.map((t) => t.id))

export function resolveChatBackgroundId(value: unknown): ChatBackgroundId | null {
  if (typeof value !== "string") return null
  if (VALID_IDS.has(value)) return value as ChatBackgroundId
  return LEGACY_CHAT_BACKGROUND_IDS[value] ?? null
}

export function isChatBackgroundId(value: unknown): value is ChatBackgroundId {
  return typeof value === "string" && VALID_IDS.has(value)
}

export const CHAT_BACKGROUND_STORAGE_KEY = "gravitre.chat.background"
