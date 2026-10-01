import { describe, expect, it } from "vitest"
import fs from "node:fs"
import path from "node:path"

const panel = fs.readFileSync(
  path.join(process.cwd(), "components/gravitre/assistant/chat-execution-panel.tsx"),
  "utf8",
)

describe("execution proof language", () => {
  it("never treats a result URL as vendor verification", () => {
    expect(panel).not.toContain("Verified — open the run overview")
    expect(panel).toContain("vendorVerified")
    expect(panel).toContain("Execution recorded")
    expect(panel).toContain("no independent vendor proof is attached yet")
  })

  it("requires explicit verification evidence for verified copy", () => {
    expect(panel).toContain("entityVerify?.verified === true")
    expect(panel).toContain("fieldVerify?.verified === true")
    expect(panel).toContain("populationVerify?.verified === true")
  })
})
