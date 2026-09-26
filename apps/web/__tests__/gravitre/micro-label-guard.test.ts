import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const ROOTS = ["app", "components"]
/** Protected chat runtime, marketing, and always-dark surfaces keep their own treatment. */
const EXCLUDED = [
  /^app[\\/](dev|deck|e2e|\(marketing\)|docs)[\\/]/,
  /^components[\\/](marketing|docs|landing|deck)[\\/]/,
  /^components[\\/]gravitre[\\/]assistant[\\/]/,
  /ai-workspace/,
  /ai-work-canvas/,
  /gravitre-command-os/,
  /chat-execution-panel/,
  /meson-wizard/,
  /settings[\\/]profile[\\/]/,
  /organization-logo/,
]
const UPPERCASE = /(?<![\w-:])uppercase(?![\w-])/
const TRACKED = /(?<![\w-])tracking-(?:wide|wider|widest|\[0?\.\d+em\])(?![\w-])/

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (name.endsWith(".tsx")) out.push(full)
  }
  return out
}

describe("shared micro-label system", () => {
  it("uses sentence-case labels instead of uppercase tracked micro-labels on product surfaces", () => {
    const offenders: string[] = []
    for (const root of ROOTS) {
      for (const file of walk(join(webRoot, root))) {
        const rel = relative(webRoot, file)
        if (EXCLUDED.some((re) => re.test(rel))) continue
        const src = readFileSync(file, "utf8")
        for (const match of src.matchAll(/(["'`])([^"'`\n]*)\1/g)) {
          const body = match[2]
          if (UPPERCASE.test(body) && TRACKED.test(body)) offenders.push(`${rel}: ${body}`)
        }
      }
    }
    expect(offenders).toEqual([])
  }, 60_000)
})
