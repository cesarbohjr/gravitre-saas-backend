import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const ROOTS = ["app", "components", "lib"]
const EXCLUDED = [/^app[\\/](dev|deck|e2e)[\\/]/, /^components[\\/]marketing[\\/]creative[\\/]/, /^lib[\\/]marketing-/]

/** Internal / build-process phrasing that must never reach customer-visible strings. */
const BANNED = [
  /never invented/i,
  /not invented/i,
  /contract-shaped/i,
  /field primacy/i,
  /One Intelligence Core/,
  /TEAM default/,
  /list and graph remain/i,
  /glow orbs/i,
  /SSE metadata/i,
  /not a separate hub tab/i,
  /old dashboard layout/i,
  /not a second dashboard/i,
  /G-STRUCT/,
  /\bSlice [0-9]/,
]

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.tsx?$/.test(name)) out.push(full)
  }
  return out
}

function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "")
    .replace(/(^|[^:"'`])\/\/.*$/gm, "$1")
}

describe("customer-visible copy guard", () => {
  it("keeps internal build language out of customer routes and components", () => {
    const offenders: string[] = []
    for (const root of ROOTS) {
      for (const file of walk(join(webRoot, root))) {
        const rel = relative(webRoot, file)
        if (EXCLUDED.some((re) => re.test(rel))) continue
        const code = stripComments(readFileSync(file, "utf8"))
        for (const re of BANNED) {
          if (re.test(code)) offenders.push(`${rel}: ${re}`)
        }
      }
    }
    expect(offenders).toEqual([])
  }, 60_000)
})
