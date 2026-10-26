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
  /** Show the tray / menu bar icon. */
  tray: boolean
  /** Quiet hours, as hours of the day (0-23); weekends are always quiet. */
  quietFrom: number
  quietTo: number
  /** Epoch ms until which notifications are paused (tray "Pause notifications for 1 hour"). */
  pausedUntil: number
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
  tray: true,
  quietFrom: 18,
  quietTo: 8,
  pausedUntil: 0,
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

/** Inside the quiet window on weekdays (6:00 PM to 8:00 AM by default), and all weekend. */
export function inQuietHours(now = new Date(), from = 18, to = 8): boolean {
  const day = now.getDay()
  if (day === 0 || day === 6) return true
  const h = now.getHours()
  return from > to ? h >= from || h < to : h >= from && h < to
}

export function hourLabel(h: number): string {
  const d = new Date(2000, 0, 1, h, 0)
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
}

/** Notifications other than failures are held: quiet hours, or paused from the tray. */
export function notificationsHeld(prefs: Prefs, now = new Date()): boolean {
  if (prefs.pausedUntil > now.getTime()) return true
  return prefs.quietHours && inQuietHours(now, prefs.quietFrom, prefs.quietTo)
}
