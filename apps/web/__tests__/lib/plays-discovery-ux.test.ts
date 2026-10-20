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
    const page = read("app/(app)/plays/page.tsx")
    expect(page).toMatch(/grant more authority when the results earn it/)
    expect(page).toMatch(/Finish setup/)
    expect(page).toMatch(/Ready to observe/)
    expect(page).not.toMatch(/EXTERNAL_CONNECTION_REQUIRED/)
  })

  it("does not introduce a second execution engine on the discovery page", () => {
    const page = read("app/(app)/plays/page.tsx")
    expect(page).not.toMatch(/Run play/)
    expect(page).not.toMatch(/\/runs`/)
    // Runs start from the play page, through the canonical workflow runtime.
    expect(page).toMatch(/href=\{`\/plays\/\$\{item\.play\.key\}`\}/)
    expect(page).toMatch(/href=\{setupHref\(item\.readiness\)\}/)
  })

  it("lists plays in the operate composition with an honest empty state", () => {
    const page = read("app/(app)/plays/page.tsx")
    expect(page).toMatch(/data-composition="operate"/)
    expect(page).toMatch(/No plays in this workspace/)
    expect(page).toMatch(/Nothing is invented when the list is empty/)
    expect(page).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
  })

  it("shows the authority an org turned on, separate from what a play has earned", () => {
    const page = read("app/(app)/plays/page.tsx")
    expect(page).toMatch(/tierOf\(/)
    expect(page).toMatch(/readinessOf\(/)
    // Granting goes through the installation API, which refuses unearned modes.
    expect(page).toMatch(/\/installation`/)
    expect(page).not.toMatch(/h \/ wk/)
  })

  it("routes missing setup to existing Gravitre surfaces", () => {
    const page = read("app/(app)/plays/page.tsx")
    const model = read("components/plays/plays-board-model.ts")
    const detail = read("app/(app)/plays/[key]/page.tsx")
    expect(page).toMatch(/href=\{setupHref\(item\.readiness\)\}/)
    expect(model).toMatch(/"\/connectors"/)
    expect(model).toMatch(/"\/workflows"/)
    expect(detail).toMatch(/href="\/connectors"/)
    expect(detail).toMatch(/href="\/workflows"/)
    expect(detail).toMatch(/Workflows remain the execution authority/)
  })
})
