/** Chat canvas wash themes — presentation preference only (localStorage). */

export const CHAT_CANVAS_THEME_IDS = [
  "slate",
  "mist",
  "pine",
  "graphite",
  "sand",
  "ink",
  "glacier",
  "midnight",
] as const

export type ChatCanvasThemeId = (typeof CHAT_CANVAS_THEME_IDS)[number]

export const CHAT_CANVAS_THEME_META: Record<
  ChatCanvasThemeId,
  { label: string; description: string }
> = {
  slate: { label: "Slate", description: "Default calm operator" },
  mist: { label: "Mist", description: "Cool soft wash" },
  pine: { label: "Pine", description: "Emerald-tinted field" },
  graphite: { label: "Graphite", description: "High-contrast graphite" },
  sand: { label: "Sand", description: "Warm restrained neutral" },
  ink: { label: "Ink", description: "Deep ink / paper" },
  glacier: { label: "Glacier", description: "Cool blue-gray" },
  midnight: { label: "Midnight", description: "Near-black stage" },
}

export const DEFAULT_CHAT_CANVAS_THEME: ChatCanvasThemeId = "slate"

const STORAGE_KEY = "gravitre.ai.chatCanvasTheme"

export function isChatCanvasThemeId(value: unknown): value is ChatCanvasThemeId {
  return typeof value === "string" && (CHAT_CANVAS_THEME_IDS as readonly string[]).includes(value)
}

export function readChatCanvasTheme(): ChatCanvasThemeId {
  if (typeof window === "undefined") return DEFAULT_CHAT_CANVAS_THEME
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (isChatCanvasThemeId(raw)) return raw
  } catch {
    /* ignore */
  }
  return DEFAULT_CHAT_CANVAS_THEME
}

export function writeChatCanvasTheme(theme: ChatCanvasThemeId): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    /* ignore */
  }
}
