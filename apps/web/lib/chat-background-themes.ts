/**
 * Gravitre chat canvas background themes.
 *
 * Soft multi-point mesh washes only — no grids, dots, hatch, or lattice.
 * Colors come from brand tokens (primary emerald, info blue, chart violet /
 * amber / coral) so light and dark stay coherent. CSS lives in globals.css
 * keyed on `.ai-chat-canvas[data-chat-bg="<id>"]`.
 */

export type ChatBackgroundId =
  | "mesh"
  | "signal"
  | "plain"
  | "aurora"
  | "bloom"
  | "dusk"
  | "tide"
  | "ember"

export type ChatBackgroundTheme = {
  id: ChatBackgroundId
  label: string
  description: string
  /** Small swatch preview used in the picker (CSS background shorthand). */
  swatch: string
}

/** Older pattern IDs → nearest mesh wash (localStorage / prefs migration). */
const LEGACY_CHAT_BACKGROUND_IDS: Record<string, ChatBackgroundId> = {
  dotgrid: "mesh",
  grid: "aurora",
  topo: "tide",
  diagonal: "aurora",
  constellation: "dusk",
  plus: "bloom",
  hex: "dusk",
  lattice: "bloom",
}

export const CHAT_BACKGROUND_THEMES: ChatBackgroundTheme[] = [
  {
    id: "mesh",
    label: "Mesh",
    description: "Soft multi-point gradient wash — emerald, blue, and violet.",
    swatch:
      "radial-gradient(circle at 18% 15%, color-mix(in oklch, var(--primary) 42%, transparent), transparent 52%), radial-gradient(circle at 78% 82%, color-mix(in oklch, var(--info) 38%, transparent), transparent 55%), radial-gradient(circle at 55% 35%, color-mix(in oklch, var(--chart-4) 28%, transparent), transparent 50%), var(--card)",
  },
  {
    id: "signal",
    label: "Signal",
    description: "Cool brand wash — primary and info, no lines or dots.",
    swatch:
      "radial-gradient(circle at 20% 10%, color-mix(in oklch, var(--primary) 40%, transparent), transparent 55%), radial-gradient(circle at 90% 90%, color-mix(in oklch, var(--info) 36%, transparent), transparent 50%), var(--card)",
  },
  {
    id: "plain",
    label: "Plain",
    description: "Clean, distraction-free surface with no wash.",
    swatch: "var(--card)",
  },
  {
    id: "aurora",
    label: "Aurora",
    description: "Icy blue into lavender and deep navy — cool diagonal bloom.",
    swatch:
      "radial-gradient(circle at 8% 8%, color-mix(in oklch, var(--accent) 55%, transparent), transparent 45%), radial-gradient(circle at 70% 20%, color-mix(in oklch, var(--info) 45%, transparent), transparent 50%), radial-gradient(circle at 92% 92%, color-mix(in oklch, var(--chart-4) 50%, transparent), transparent 48%), var(--card)",
  },
  {
    id: "bloom",
    label: "Bloom",
    description: "Mint to sky to mauve to peach — warm multi-hue mesh.",
    swatch:
      "radial-gradient(circle at 10% 12%, color-mix(in oklch, var(--primary) 38%, transparent), transparent 48%), radial-gradient(circle at 40% 20%, color-mix(in oklch, var(--info) 36%, transparent), transparent 50%), radial-gradient(circle at 48% 55%, color-mix(in oklch, var(--chart-4) 40%, transparent), transparent 48%), radial-gradient(circle at 92% 55%, color-mix(in oklch, var(--chart-5) 42%, transparent), transparent 50%), var(--card)",
  },
  {
    id: "dusk",
    label: "Dusk",
    description: "Cream into soft periwinkle — quiet evening wash.",
    swatch:
      "radial-gradient(circle at 15% 10%, color-mix(in oklch, var(--chart-3) 35%, transparent), transparent 48%), radial-gradient(circle at 55% 40%, color-mix(in oklch, var(--accent) 40%, transparent), transparent 52%), radial-gradient(circle at 88% 88%, color-mix(in oklch, var(--info) 48%, transparent), transparent 50%), var(--card)",
  },
  {
    id: "tide",
    label: "Tide",
    description: "Soft emerald sea wash — primary with a cool info undertone.",
    swatch:
      "radial-gradient(circle at 25% 80%, color-mix(in oklch, var(--primary) 44%, transparent), transparent 55%), radial-gradient(circle at 80% 15%, color-mix(in oklch, var(--info) 32%, transparent), transparent 50%), radial-gradient(circle at 50% 40%, color-mix(in oklch, var(--chart-1) 28%, transparent), transparent 55%), var(--card)",
  },
  {
    id: "ember",
    label: "Ember",
    description: "Warm amber and coral haze with a touch of emerald.",
    swatch:
      "radial-gradient(circle at 20% 25%, color-mix(in oklch, var(--chart-3) 40%, transparent), transparent 50%), radial-gradient(circle at 85% 70%, color-mix(in oklch, var(--chart-5) 38%, transparent), transparent 52%), radial-gradient(circle at 45% 85%, color-mix(in oklch, var(--primary) 22%, transparent), transparent 48%), var(--card)",
  },
]

export const DEFAULT_CHAT_BACKGROUND: ChatBackgroundId = "mesh"

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
