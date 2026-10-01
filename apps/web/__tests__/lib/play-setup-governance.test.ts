import fs from "node:fs"
import path from "node:path"

const root = process.cwd()
const read = (relative: string) => fs.readFileSync(path.join(root, relative), "utf8")

describe("Play setup and governance UX", () => {
  it("persists tenant Play setup through the org-scoped installation API", () => {
    const route = read("app/api/plays/[key]/installation/route.ts")
    expect(route).toMatch(/resolveOrgId/)
    expect(route).toMatch(/play_installations/)
    expect(route).toMatch(/org_id:\s*orgId/)
    expect(route).toMatch(/onConflict:\s*"org_id,environment_name,play_key"/)
  })

  it("uses progressive authority instead of an autonomous toggle", () => {
    const setup = read("components/plays/play-setup.tsx")
    expect(setup).toMatch(/Observe/)
    expect(setup).toMatch(/Recommend/)
    expect(setup).toMatch(/Act with approval/)
    expect(setup).toMatch(/Act within policy/)
    expect(setup).not.toMatch(/Autonomous/)
  })

  it("cannot select authority that readiness has not earned", () => {
    const setup = read("components/plays/play-setup.tsx")
    expect(setup).toMatch(/availableModes/)
    expect(setup).toMatch(/disabled=!\{enabled\}|disabled=\{!enabled\}/)
    expect(setup).toMatch(/Complete readiness requirements first/)
  })

  it("links a Play to an existing Goal without duplicating Goal storage", () => {
    const setup = read("components/plays/play-setup.tsx")
    expect(setup).toMatch(/useSWR<\{ goals: Goal\[\] \}>\("\/api\/goals"/)
    expect(setup).toMatch(/goalId/)
    expect(setup).toMatch(/No linked goal/)
  })

  it("still does not expose execution in Slice 3", () => {
    const setup = read("components/plays/play-setup.tsx")
    const detail = read("app/plays/[key]/page.tsx")
    expect(setup).not.toMatch(/Run play/)
    expect(detail).not.toMatch(/Run play/)
  })
})
