import type { DashboardLayout } from "./types"
import { createDefaultLayout } from "./kpi-registry"

const STORAGE_PREFIX = "gravitre:dashboard-layout:v1"

export function storageKey(orgId: string, userId: string): string {
  return `${STORAGE_PREFIX}:${orgId}:${userId}`
}

export function readLocalLayout(orgId: string, userId: string): DashboardLayout | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(storageKey(orgId, userId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as DashboardLayout
    if (parsed?.version !== 1 || !Array.isArray(parsed.widgets)) return null
    return parsed
  } catch {
    return null
  }
}

export function writeLocalLayout(orgId: string, userId: string, layout: DashboardLayout): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      storageKey(orgId, userId),
      JSON.stringify({ ...layout, updatedAt: new Date().toISOString() }),
    )
  } catch {
    // quota / private mode — ignore
  }
}

export function clearLocalLayout(orgId: string, userId: string): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(storageKey(orgId, userId))
  } catch {
    // ignore
  }
}

export async function fetchRemoteLayout(): Promise<DashboardLayout | null> {
  try {
    const res = await fetch("/api/settings/dashboard-layout", { credentials: "include" })
    if (!res.ok) return null
    const body = (await res.json()) as { layout?: DashboardLayout | null }
    if (body.layout?.version === 1 && Array.isArray(body.layout.widgets)) {
      return body.layout
    }
    return null
  } catch {
    return null
  }
}

export async function saveRemoteLayout(layout: DashboardLayout): Promise<boolean> {
  try {
    const res = await fetch("/api/settings/dashboard-layout", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout }),
    })
    return res.ok
  } catch {
    return false
  }
}

export function resolveInitialLayout(
  orgId: string | null,
  userId: string | null,
): DashboardLayout {
  if (orgId && userId) {
    const local = readLocalLayout(orgId, userId)
    if (local) return local
  }
  return createDefaultLayout()
}
