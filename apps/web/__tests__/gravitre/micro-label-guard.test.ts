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
  /organization-logo/,
  /fleet-prototype-shell/,
]
const UPPERCASE = /(?<![\w-:])uppercase(?![\w-])/
const TITLE_CASE_TEXT = />\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*</g
const PROPER_NAMES = [
  /^John Doe$/,
  /^Sarah Chen$/,
  /^Acme\b/,
  /^(United States|European Union|Pacific Time)$/,
  /^Gravitre (Certified|Marketplace|Labs|Desktop|Lite)$/,
  /^Stripe Connect$/,
  /^Model Studio$/,
  /^Agent Council$/,
  /^Intelligence Core$/,
  /^(Gravitre|Meson|Slack|Stripe|Google|Microsoft|Apollo|Salesforce) [A-Z][a-z]+$/,
  /\b(Gravitre|Meson|Agent Council)\b/,
]

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) walk(full, out)
    else if (name.endsWith(".tsx")) out.push(full)
  }
  return out
}

describe("shared micro-label system", () => {
  it("uses sentence-case labels instead of uppercase micro-labels on product surfaces", () => {
    const offenders: string[] = []
    for (const root of ROOTS) {
      for (const file of walk(join(webRoot, root))) {
        const rel = relative(webRoot, file)
        if (EXCLUDED.some((re) => re.test(rel))) continue
        const src = readFileSync(file, "utf8")
        for (const match of src.matchAll(/(["'`])([^"'`]*)\1/g)) {
          const body = match[2]
          if (/[<>{}();=]/.test(body)) continue
          if (UPPERCASE.test(body)) offenders.push(`${rel}: ${body.trim().slice(0, 80)}`)
        }
      }
    }
    expect(offenders).toEqual([])
  }, 60_000)

  it("renders visible JSX labels in sentence case (master spec 9.1)", () => {
    const offenders: string[] = []
    for (const root of ROOTS) {
      for (const file of walk(join(webRoot, root))) {
        const rel = relative(webRoot, file)
        if (EXCLUDED.some((re) => re.test(rel))) continue
        const src = readFileSync(file, "utf8")
        for (const match of src.matchAll(TITLE_CASE_TEXT)) {
          const text = match[1]
          if (PROPER_NAMES.some((re) => re.test(text))) continue
          offenders.push(`${rel}: ${text}`)
        }
      }
    }
    expect(offenders).toEqual([])
  }, 60_000)
})
