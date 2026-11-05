import { GV_PROVIDERS } from "./providers.generated"

export type ProviderMark = { id: string; name: string; src: string; srcDark: string; lightPlate: boolean; darkPlate: boolean }

/**
 * The web app's official mark for a connector type, vendor key, tool prefix or
 * name (see providers.generated.ts). Null when the registry has none.
 */
export function providerMark(slug: string | null | undefined): ProviderMark | null {
  const raw = String(slug || "").toLowerCase()
  if (!raw.trim()) return null
  const tries = [raw, raw.split(/[._:\s-]/)[0]]
  for (const t of tries) {
    const id = GV_PROVIDERS.lookup[t.replace(/[^a-z0-9]/g, "")]
    const e = id ? GV_PROVIDERS.entries[id] : undefined
    if (id && e) return { id, name: e[0], src: e[1], srcDark: e[2], lightPlate: Boolean(e[3]), darkPlate: Boolean(e[4]) }
  }
  return null
}
