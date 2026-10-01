import fs from "node:fs"
import path from "node:path"

const root = process.cwd()
const read = (relative: string) => fs.readFileSync(path.join(root, relative), "utf8")

describe("Play execution UX", () => {
  it("runs only a saved approval-governed installation", () => {
    const control = read("components/plays/play-run-control.tsx")
    expect(control).toMatch(/ACT WITH APPROVAL/)
    expect(control).toMatch(/act_with_approval_ready/)
    expect(control).toMatch(/installation\.status === "ready"/)
    expect(control).toMatch(/Run play/)
  })

  it("does not present observe or recommend as external execution", () => {
    const control = read("components/plays/play-run-control.tsx")
    expect(control).toMatch(/does not take external action/)
  })

  it("keeps act-within-policy locked until runtime authorization is proven", () => {
    const control = read("components/plays/play-run-control.tsx")
    expect(control).toMatch(/effective runtime action authorization/)
  })
})
