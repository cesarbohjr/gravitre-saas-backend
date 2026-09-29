import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")

describe("Model Studio external dataset connectors", () => {
  it("uses the training provider API without auto-materialization", () => {
    const api = readFileSync(resolve(webRoot, "lib/api.ts"), "utf8")
    expect(api).toMatch(/\/api\/training\/external-datasets\/providers/)
    expect(api).toMatch(/\/api\/training\/external-datasets\/search/)
    expect(api).toMatch(/\/api\/training\/external-datasets\/inspect/)
  })

  it("labels discovered datasets as reference-only", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/External dataset connectors/)
    expect(studio).toMatch(/REFERENCE ONLY/)
    expect(studio).toMatch(/Nothing is downloaded or added to training automatically/)
  })
})
