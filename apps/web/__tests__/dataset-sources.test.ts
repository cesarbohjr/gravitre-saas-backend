import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "..")
const read = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

describe("provider-neutral dataset sources", () => {
  it("uses the canonical training dataset source endpoints", () => {
    const api = read("lib/api.ts")
    expect(api).toMatch(/\/api\/training\/datasets\/\$\{datasetId\}\/sources/)
    expect(api).toMatch(/providerSpecificBehavior/)
    expect(api).toMatch(/materializationAutomatic/)
  })

  it("keeps external source inspection inside Model Studio", () => {
    const studio = read("components/intelligence/pages/model-studio-stage.tsx")
    expect(studio).toMatch(/External sources/)
    expect(studio).toMatch(/Provider-neutral references/)
    expect(studio).toMatch(/materialization is explicitly requested/)
  })

  it("does not hardcode a provider-specific product path", () => {
    const api = read("lib/api.ts").toLowerCase()
    const studio = read("components/intelligence/pages/model-studio-stage.tsx").toLowerCase()
    expect(api).not.toMatch(/huggingface|kaggle/)
    expect(studio).not.toMatch(/huggingface|kaggle/)
  })
})
