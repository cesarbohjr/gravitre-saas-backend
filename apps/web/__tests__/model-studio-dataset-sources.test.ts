import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const read = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

describe("Model Studio external dataset sources", () => {
  it("uses the existing training dataset APIs rather than a second dataset product", () => {
    const api = read("lib/api.ts")
    expect(api).toMatch(/\/api\/training\/datasets\/\$\{datasetId\}\/sources/)
    expect(api).toMatch(/sampleDatasetSource/)
    expect(api).not.toMatch(/\/api\/dataset-providers/)
  })

  it("keeps Hugging Face sampling bounded and non-materializing in Model Studio", () => {
    const studio = read("components/intelligence/pages/model-studio-stage.tsx")
    expect(studio).toMatch(/Add Hugging Face source/)
    expect(studio).toMatch(/Sample mode only/)
    expect(studio).toMatch(/No full download, materialization, or credential storage/)
    expect(studio).toMatch(/not materialized/)
    expect(studio).not.toMatch(/access token|api key|password/i)
  })
})
