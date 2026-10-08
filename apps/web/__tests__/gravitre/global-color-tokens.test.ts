import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, resolve } from "node:path"
import { describe, expect, it } from "vitest"

/**
 * Colour comes from the global theme tokens in app/globals.css (success, warning,
 * info, destructive, brand, primary, muted, chart-N, status-*), so light and dark
 * themes and the marketing canvas stay consistent. Raw Tailwind palette classes
 * bypass the themes. `gray-*` is excluded because the theme redefines that ramp.
 */
const webRoot = resolve(__dirname, "../..")
const ROOTS = ["app", "components", "lib", "hooks"]
const RAW_PALETTE =
  /\b(?:bg|text|border|from|to|via|ring|fill|stroke|outline|divide|shadow|decoration|placeholder|caret|accent)-(?:blue|indigo|purple|violet|pink|rose|cyan|sky|teal|orange|amber|yellow|lime|green|emerald|red|fuchsia|slate|zinc|neutral|stone)-\d{2,3}\b/g

/** Deliberately distinct colours, each with its reason. */
const ALLOWED: Record<string, string> = {
  "lib/agent-identity.ts": "per-agent identity hues",
  "lib/agent-identity-bridge.ts": "maps legacy classes onto identity hues",
  "lib/agent-display.ts": "per-agent identity hues",
  "lib/department-gradient.ts": "per-department identity gradients",
  "lib/assignments.ts": "per-department identity gradients",
  "lib/assignments-list.ts": "per-department identity gradients",
  "lib/supabase/demo-bootstrap.ts": "seeded agent identity colours",
  "lib/e2e-shot-fixtures.ts": "screenshot fixture data",
  "components/agents/fleet-v4/identity-tokens.ts": "per-agent identity hues",
  "components/agents/fleet-v4/current-vs-proposed.tsx": "agent avatar identity colours",
  "components/gravitre/agent-identity-editor.tsx": "agent identity colour ids",
  "components/gravitre/meson-wizard.tsx": "agent identity colour ids",
  "components/gravitre/chat-avatars.tsx": "per-agent avatar hues",
  "components/gravitre/organization-logo.tsx": "per-organisation identity gradients",
  "components/docs/mdx-client.tsx": "always-dark code block",
  "components/docs/mdx-elements.tsx": "dark product window frame and window-control dots",
  "app/(marketing)/api/page.tsx": "code syntax highlighting",
  "app/(app)/settings/billing/page.tsx": "payment card illustration",
  "components/intelligence/intelligence-sparkline.tsx": "class names quoted in a comment",
}

function walk(dir: string, out: string[]) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name)
    const rel = relative(webRoot, full)
    if (rel === "app/e2e" || rel === "app/dev" || name === "node_modules") continue
    if (statSync(full).isDirectory()) walk(full, out)
    else if (/\.(tsx|ts)$/.test(name) && !name.endsWith(".d.ts")) out.push(rel)
  }
  return out
}

describe("global colour tokens", () => {
  const files = ROOTS.flatMap((root) => walk(resolve(webRoot, root), []))

  it("web app and marketing site use theme tokens, not raw palette colours", () => {
    const offenders = files
      .filter((file) => !(file in ALLOWED))
      .map((file) => ({ file, hits: readFileSync(resolve(webRoot, file), "utf8").match(RAW_PALETTE) ?? [] }))
      .filter(({ hits }) => hits.length > 0)
      .map(({ file, hits }) => `${file}: ${[...new Set(hits)].join(", ")}`)
    expect(offenders).toEqual([])
  })

  it("every allowlisted file still exists", () => {
    const set = new Set(files)
    expect(Object.keys(ALLOWED).filter((file) => !set.has(file))).toEqual([])
  })

  it("marketing canvas tokens resolve in the light theme", () => {
    const css = readFileSync(resolve(webRoot, "app/globals.css"), "utf8")
    const root = css.slice(css.indexOf(":root {"), css.indexOf(".dark {"))
    expect(root).toContain("--g-marketing-canvas:")
    expect(root).toContain("--g-marketing-surface:")
  })
})
