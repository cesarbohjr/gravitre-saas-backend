/**
 * Gravitre chat canvas background themes.
 *
 * Subtle, business/operator-appropriate textures that sit BEHIND the chat
 * transcript. Geometric options (Blueprint, Dot grid, Plus, Hex, Lattice)
 * follow the Hero Patterns tradition — small, restrained, MIT-licensed motifs
 * recolored onto Gravitre ink/background tokens. Organic options (Contour,
 * Mesh) stay soft and data-adjacent. CSS lives in globals.css keyed on
 * `.ai-chat-canvas[data-chat-bg="<id>"]` so every pattern adapts to light/dark
 * and keeps message bubbles/text legible.
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
  | "plus"
  | "hex"
  | "lattice"

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
  {
    id: "plus",
    label: "Plus",
    description: "Sparse plus marks — Hero Patterns technical, low contrast.",
    swatch:
      "linear-gradient(to right, transparent calc(50% - 0.5px), color-mix(in oklch, var(--foreground) 22%, transparent) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px)) 0 0 / 14px 5px, linear-gradient(to bottom, transparent calc(50% - 0.5px), color-mix(in oklch, var(--foreground) 22%, transparent) calc(50% - 0.5px) calc(50% + 0.5px), transparent calc(50% + 0.5px)) 0 0 / 5px 14px, var(--card)",
  },
  {
    id: "hex",
    label: "Hex",
    description: "Honeycomb lattice — geometric and quietly structural.",
    swatch:
      "linear-gradient(30deg, color-mix(in oklch, var(--border) 80%, transparent) 1px, transparent 1px) 0 0 / 12px 20px, linear-gradient(90deg, color-mix(in oklch, var(--border) 80%, transparent) 1px, transparent 1px) 0 0 / 12px 20px, linear-gradient(150deg, color-mix(in oklch, var(--border) 80%, transparent) 1px, transparent 1px) 0 0 / 12px 20px, var(--card)",
  },
  {
    id: "lattice",
    label: "Lattice",
    description: "Open square cells — like a light schematic frame.",
    swatch:
      "linear-gradient(color-mix(in oklch, var(--foreground) 20%, transparent) 1px, transparent 1px) 0 0 / 16px 16px, linear-gradient(90deg, color-mix(in oklch, var(--foreground) 20%, transparent) 1px, transparent 1px) 0 0 / 16px 16px, var(--card)",
  },
]

export const DEFAULT_CHAT_BACKGROUND: ChatBackgroundId = "signal"

const VALID_IDS = new Set<string>(CHAT_BACKGROUND_THEMES.map((t) => t.id))

export function isChatBackgroundId(value: unknown): value is ChatBackgroundId {
  return typeof value === "string" && VALID_IDS.has(value)
}

export const CHAT_BACKGROUND_STORAGE_KEY = "gravitre.chat.background"
