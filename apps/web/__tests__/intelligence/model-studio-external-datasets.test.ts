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


  it("selects providers from the canonical registry instead of hardcoding one adapter", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/externalProviderId/)
    expect(studio).toMatch(/trainingApi\.searchExternalDatasets\(externalProviderId/)
    expect(studio).toMatch(/External dataset provider/)
    expect(studio).not.toMatch(/searchExternalDatasets\("huggingface"/)
    expect(studio).not.toMatch(/placeholder="Search Hugging Face datasets"/)
  })


describe("Model Studio external dataset reference binding", () => {
  it("inspects provider metadata before creating a reference", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/trainingApi\.inspectExternalDataset\(externalProviderId, selectedExternalDatasetId\)/)
    expect(studio).toMatch(/data-review-surface="external-dataset-inspect"/)
    expect(studio).toMatch(/materialized: no/)
  })

  it("uses the existing admin-protected reference API with explicit purpose and target", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/trainingApi\.createExternalDatasetReference/)
    expect(studio).toMatch(/purpose: externalPurpose/)
    expect(studio).toMatch(/targetType: externalTargetType/)
    expect(studio).toMatch(/targetId: externalTargetId\.trim\(\)/)
    expect(studio).toMatch(/accessMode: "reference"/)
  })

  it("does not imply that adding a reference downloads or trains on provider content", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/does not download, index, train, or fine-tune/)
    expect(studio).not.toMatch(/materializeExternalDataset/)
    expect(studio).not.toMatch(/downloadExternalDataset/)
  })

  it("keeps restricted datasets non-selectable", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/disabled=\{restricted\}/)
    expect(studio).toMatch(/RESTRICTED/)
  })
})
