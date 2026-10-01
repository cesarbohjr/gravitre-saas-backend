import fs from "node:fs"
import path from "node:path"

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

  it("does not introduce a second execution button in discovery slice", () => {
    const page = read("app/plays/page.tsx")
    const detail = read("app/plays/\[key\]/page.tsx")
    expect(page).not.toMatch(/Run play/)
    expect(detail).not.toMatch(/Run play/)
    expect(detail).toMatch(/Workflows remain the execution authority/)
  })

  it("routes missing setup to existing Gravitre surfaces", () => {
    const page = read("app/plays/page.tsx")
    const detail = read("app/plays/\[key\]/page.tsx")
    expect(page).toMatch(/href=\{setupHref\(readiness\)\}/)
    expect(detail).toMatch(/href="\/connectors"/)
    expect(detail).toMatch(/href="\/workflows"/)
  })
})
