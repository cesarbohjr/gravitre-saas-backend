import fs from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const root = process.cwd()
const read = (relative: string) => fs.readFileSync(path.join(root, relative), "utf8")

describe("Play setup and governance UX", () => {
  it("persists tenant Play setup through the org-scoped installation API", () => {
    const route = read("app/api/plays/[key]/installation/route.ts")
    const backend = read("../../backend/app/routers/plays.py")
    expect(route).toMatch(/proxyToFastApi/)
    expect(route).toMatch(/\/api\/plays\/\$\{encodeURIComponent\(key\)\}\/installation/)
    expect(backend).toMatch(/play_installations/)
    expect(backend).toMatch(/eq\("org_id", org_id\)/)
    expect(backend).toMatch(/on_conflict="org_id,environment_name,play_key"/)
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
    expect(setup).toMatch(/disabled=\{!enabled\}/)
    expect(setup).toMatch(/Complete readiness requirements first/)
  })

  it("links a Play to an existing Goal without duplicating Goal storage", () => {
    const setup = read("components/plays/play-setup.tsx")
    expect(setup).toMatch(/useSWR<\{ goals: Goal\[\] \}>\("\/api\/goals"/)
    expect(setup).toMatch(/goalId/)
    expect(setup).toMatch(/No linked goal/)
  })

  it("keeps Run play on the governed execution control, not an autonomous toggle", () => {
    const setup = read("components/plays/play-setup.tsx")
    const control = read("components/plays/play-run-control.tsx")
    expect(setup).not.toMatch(/Run play/)
    expect(control).toMatch(/Run play/)
    expect(control).toMatch(/existing approval queue/)
  })
})
