import fs from "node:fs"
import path from "node:path"

const REPO_ROOT = path.resolve(__dirname, "..")

function parseDotenv(content: string): Record<string, string> {
  const env: Record<string, string> = {}
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) continue
    const eq = trimmed.indexOf("=")
    if (eq <= 0) continue
    const key = trimmed.slice(0, eq).trim()
    let value = trimmed.slice(eq + 1).trim()
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }
    env[key] = value
  }
  return env
}

function loadFile(relativePath: string): Record<string, string> {
  const filePath = path.join(REPO_ROOT, relativePath)
  if (!fs.existsSync(filePath)) return {}
  return parseDotenv(fs.readFileSync(filePath, "utf8"))
}

/** Merge repo env files for Playwright webServer processes (does not override process.env). */
export function loadE2eEnv(): Record<string, string> {
  const merged = {
    ...loadFile("backend/.env"),
    ...loadFile("backend/.env.operator.local"),
    ...loadFile("apps/web/.env.local"),
  }

  if (merged.SUPABASE_URL && !merged.NEXT_PUBLIC_SUPABASE_URL) {
    merged.NEXT_PUBLIC_SUPABASE_URL = merged.SUPABASE_URL
  }
  if (merged.SUPABASE_ANON_KEY && !merged.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
    merged.NEXT_PUBLIC_SUPABASE_ANON_KEY = merged.SUPABASE_ANON_KEY
  }
  if (!merged.FASTAPI_BASE_URL) {
    merged.FASTAPI_BASE_URL = "http://127.0.0.1:8000"
  }

  return merged
}

export function mergeE2eProcessEnv(): Record<string, string> {
  return { ...loadE2eEnv(), ...process.env }
}
