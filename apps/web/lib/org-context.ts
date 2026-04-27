export const DEFAULT_DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
export const SECONDARY_DEMO_ORG_ID = "11111111-1111-4111-8111-111111111111"

export const ORG_STORAGE_KEY = "gravitre:selectedOrg"

export interface SelectedOrg {
  id: string
  name: string
}

export function getSelectedOrgFromStorage(): SelectedOrg | null {
  if (typeof window === "undefined") return null
  const raw = window.localStorage.getItem(ORG_STORAGE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<SelectedOrg>
    if (!parsed.id || !parsed.name) return null
    return { id: parsed.id, name: parsed.name }
  } catch {
    return null
  }
}

export function setSelectedOrgInStorage(org: SelectedOrg) {
  if (typeof window === "undefined") return
  window.localStorage.setItem(ORG_STORAGE_KEY, JSON.stringify(org))
}
