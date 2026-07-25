/**
 * Gravitre chat canvas background themes.
 *
 * Eight subtle, business/operator-appropriate textures that sit BEHIND the
 * chat transcript. Each theme is a barely-there geometric or data-adjacent
 * motif — never a literal social-media doodle. The actual CSS lives in
 * globals.css keyed on `.ai-chat-canvas[data-chat-bg="<id>"]`, driven by theme
 * tokens so every pattern adapts to both light and dark automatically and
 * keeps message bubbles/text legible at every breakpoint.
 */

export type ChatBackgroundId =
  | "signal"
  | "plain"
  | "dotgrid"
  | "grid"
  | "topo"
  | "mesh"
  | "diagonal"
  | "constellation"

export type ChatBackgroundTheme = {
  id: ChatBackgroundId
  label: string
  description: string
  /** Small swatch preview used in the picker (CSS background shorthand). */
  swatch: string
}

export const CHAT_BACKGROUND_THEMES: ChatBackgroundTheme[] = [
  {
    id: "signal",
    label: "Signal",
    description: "Emerald + blue tints over a soft dot-grid — the Gravitre default.",
    swatch:
      "radial-gradient(circle at 25% 20%, color-mix(in oklch, var(--primary) 30%, transparent), transparent 60%), radial-gradient(color-mix(in oklch, var(--primary) 22%, transparent) 1px, transparent 1px) 0 0 / 8px 8px, var(--card)",
  },
  {
    id: "plain",
    label: "Plain",
    description: "Clean, distraction-free surface with no pattern.",
    swatch: "var(--card)",
  },
  {
    id: "dotgrid",
    label: "Dot grid",
    description: "Evenly spaced dots — calm, technical, low contrast.",
    swatch:
      "radial-gradient(color-mix(in oklch, var(--foreground) 28%, transparent) 1px, transparent 1px) 0 0 / 7px 7px, var(--card)",
  },
  {
    id: "grid",
    label: "Blueprint",
    description: "Fine line grid, like engineering graph paper.",
    swatch:
      "linear-gradient(var(--border) 1px, transparent 1px) 0 0 / 8px 8px, linear-gradient(90deg, var(--border) 1px, transparent 1px) 0 0 / 8px 8px, var(--card)",
  },
  {
    id: "topo",
    label: "Contour",
    description: "Abstract topographic waves — data-adjacent and quiet.",
    swatch:
      "repeating-radial-gradient(circle at 30% 120%, transparent 0 5px, color-mix(in oklch, var(--info) 24%, transparent) 5px 6px), var(--card)",
  },
  {
    id: "mesh",
    label: "Mesh",
    description: "Soft multi-point gradient wash, no lines or dots.",
    swatch:
      "radial-gradient(circle at 20% 20%, color-mix(in oklch, var(--primary) 34%, transparent), transparent 55%), radial-gradient(circle at 80% 80%, color-mix(in oklch, var(--info) 30%, transparent), transparent 55%), var(--card)",
  },
  {
    id: "diagonal",
    label: "Hatch",
    description: "Subtle diagonal hatch lines for a printed, precise feel.",
    swatch:
      "repeating-linear-gradient(45deg, color-mix(in oklch, var(--foreground) 16%, transparent) 0 1px, transparent 1px 6px), var(--card)",
  },
  {
    id: "constellation",
    label: "Network",
    description: "Sparse connected nodes — a nod to knowledge graphs.",
    swatch:
      "radial-gradient(circle at 30% 35%, color-mix(in oklch, var(--primary) 40%, transparent) 1.5px, transparent 2px), radial-gradient(circle at 70% 65%, color-mix(in oklch, var(--info) 40%, transparent) 1.5px, transparent 2px), var(--card)",
  },
]

export const DEFAULT_CHAT_BACKGROUND: ChatBackgroundId = "signal"

const VALID_IDS = new Set<string>(CHAT_BACKGROUND_THEMES.map((t) => t.id))

export function isChatBackgroundId(value: unknown): value is ChatBackgroundId {
  return typeof value === "string" && VALID_IDS.has(value)
}

export const CHAT_BACKGROUND_STORAGE_KEY = "gravitre.chat.background"
