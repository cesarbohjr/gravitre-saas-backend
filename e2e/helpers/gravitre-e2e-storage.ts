import fs from "node:fs"
import path from "node:path"
import type { BrowserContext } from "@playwright/test"

/** Persist only via GRAVITRE_E2E_STORAGE_STATE — never commit the file. */
export function e2eStorageStatePath(): string | null {
  const fromEnv = (process.env.GRAVITRE_E2E_STORAGE_STATE || "").trim()
  if (fromEnv) return path.resolve(fromEnv)
  const fallback = path.resolve(__dirname, "..", ".fixtures", "gravitre-e2e-storage.json")
  if (fs.existsSync(fallback)) return fallback
  return null
}

export function hasE2eStorageState(): boolean {
  const p = e2eStorageStatePath()
  return Boolean(p && fs.existsSync(p))
}

export async function applyE2eStorageState(context: BrowserContext) {
  const p = e2eStorageStatePath()
  if (!p) throw new Error("GRAVITRE_E2E_STORAGE_STATE is not set")
  const raw = JSON.parse(fs.readFileSync(p, "utf8")) as { cookies?: unknown; origins?: unknown }
  if (!raw.cookies && !raw.origins) {
    throw new Error("storage state file is empty")
  }
}
