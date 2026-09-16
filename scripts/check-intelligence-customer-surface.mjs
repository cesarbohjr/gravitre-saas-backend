#!/usr/bin/env node
/**
 * I11 — Customer Intelligence surface guards.
 *
 * 1) No raw quality-flag tokens in customer Intelligence UI unless the file
 *    maps them through qualityFlagToCopy.
 * 2) No imports of /admin/intelligence from customer Intelligence routes/components.
 */
import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, relative } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WEB = join(ROOT, "apps", "web")

const SCAN_ROOTS = [
  join(WEB, "app", "intelligence"),
  join(WEB, "components", "intelligence"),
]

const RAW_FLAGS = ["INSUFFICIENT_DATA", "NOT_CONFIGURED"]
const ADMIN_IMPORT = /@\/app\/admin\/intelligence/

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next") continue
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, out)
    else if (/\.(tsx|ts)$/.test(name) && !name.includes(".test.")) out.push(p)
  }
  return out
}

const files = SCAN_ROOTS.flatMap((dir) => walk(dir))
const failures = []

for (const file of files) {
  const rel = relative(WEB, file).replace(/\\/g, "/")
  const src = readFileSync(file, "utf8")

  if (ADMIN_IMPORT.test(src)) {
    failures.push(`${rel}: imports admin Intelligence console — customer surfaces must not`)
  }

  const usesCopyHelper = src.includes("qualityFlagToCopy") || src.includes("formatQualityFlagsHuman")
  for (const flag of RAW_FLAGS) {
    if (src.includes(`"${flag}"`) || src.includes(`'${flag}'`)) {
      if (!usesCopyHelper) {
        failures.push(`${rel}: raw ${flag} without qualityFlagToCopy / formatQualityFlagsHuman`)
      }
    }
  }
}

if (failures.length) {
  console.error("Intelligence customer surface guard failed:\n" + failures.map((row) => `  - ${row}`).join("\n"))
  process.exit(1)
}

console.log(`Intelligence customer surface guard: PASS (${files.length} files)`)
