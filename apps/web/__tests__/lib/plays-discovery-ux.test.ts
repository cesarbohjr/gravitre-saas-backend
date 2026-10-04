import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const root = process.cwd()
const read = (relative: string) => fs.readFileSync(path.join(root, relative), "utf8")

describe("Plays discovery UX", () => {
  it("exposes Plays beside Goals as an operating surface", () => {
    const nav = read("components/gravitre/sidebar-nav-config.ts")
    const routes = read("lib/app-routes.ts")
    expect(routes).toMatch(/plays:\s*"\/plays"/)
    expect(nav).toMatch(/name:\s*"Goals"/)
    expect(nav).toMatch(/name:\s*"Plays".*APP_ROUTES\.plays/)
  })

  it("keeps outcome language ahead of implementation language", () => {
    const page = read("app/plays/page.tsx")
    expect(page).toMatch(/Turn business goals into coordinated action/)
    expect(page).toMatch(/Finish setup/)
    expect(page).toMatch(/Ready to observe/)
    expect(page).not.toMatch(/EXTERNAL_CONNECTION_REQUIRED/)
  })

  it("does not introduce a second execution engine on the discovery page", () => {
    const page = read("app/plays/page.tsx")
    expect(page).not.toMatch(/Run play/)
    expect(page).toMatch(/href=\{setupHref\(readiness\)\}/)
  })

  it("lists plays as operating rows without elevated cards", () => {
    const page = read("app/plays/page.tsx")
    expect(page).toMatch(/data-composition="operate"/)
    expect(page).toMatch(/divide-y divide-divide border-y border-divide/)
    expect(page).toMatch(/No plays in this workspace/)
    expect(page).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(page).not.toMatch(/lg:grid-cols-3/)
  })

  it("routes missing setup to existing Gravitre surfaces", () => {
    const page = read("app/plays/page.tsx")
    const detail = read("app/plays/[key]/page.tsx")
    expect(page).toMatch(/href=\{setupHref\(readiness\)\}/)
    expect(detail).toMatch(/href="\/connectors"/)
    expect(detail).toMatch(/href="\/workflows"/)
    expect(detail).toMatch(/Workflows remain the execution authority/)
  })
})
