/** Settings for this computer only. Account, workspace and policies live on the web. */
export type ThemePick = "light" | "dark" | "system"

export type Prefs = {
  theme: ThemePick
  railWide: boolean
  notifyApprovals: boolean
  notifyDone: boolean
  notifyFailed: boolean
  quietHours: boolean
  micId: string
  agentId: string
}

const KEY = "gravitre.desktop.prefs"

export const DEFAULT_PREFS: Prefs = {
  theme: "system",
  railWide: true,
  notifyApprovals: true,
  notifyDone: false,
  notifyFailed: true,
  quietHours: false,
  micId: "",
  agentId: "",
}

export function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<Prefs>) } : DEFAULT_PREFS
  } catch {
    return DEFAULT_PREFS
  }
}

export function savePrefs(prefs: Prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs))
  } catch {
    /* private mode */
  }
}

/** 6:00 PM to 8:00 AM on weekdays, and all weekend. */
export function inQuietHours(now = new Date()): boolean {
  const day = now.getDay()
  if (day === 0 || day === 6) return true
  const h = now.getHours()
  return h >= 18 || h < 8
}
