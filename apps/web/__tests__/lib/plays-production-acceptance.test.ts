import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const read = (p: string) => fs.readFileSync(path.join(process.cwd(), p), "utf8")

describe("Plays production acceptance", () => {
  it("keeps all six layers discoverable and linked", () => {
    const nav = read("components/gravitre/sidebar-nav-config.ts")
    const routes = read("lib/app-routes.ts")
    const page = read("app/(app)/plays/page.tsx")
    expect(routes).toMatch(/plays: "\/plays"/)
    expect(nav).toMatch(/APP_ROUTES\.plays/)
    expect(page).toMatch(/Turn business goals into coordinated action/)
  })

  it("keeps action authority in canonical workflows", () => {
    const run = read("components/plays/play-run-control.tsx")
    expect(run).toMatch(/existing approval queue/)
    expect(run).toMatch(/effective runtime action authorization/)
  })

  it("keeps outcome truth visible to users", () => {
    const results = read("components/plays/play-results.tsx")
    const dashboard = read("components/home/v3/play-outcomes.tsx")
    expect(results).toMatch(/completed action is not counted as business impact/)
    expect(dashboard).toMatch(/Verified Play impact/)
  })
})
