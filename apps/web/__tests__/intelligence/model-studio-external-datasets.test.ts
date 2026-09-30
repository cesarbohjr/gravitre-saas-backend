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
    expect(studio).toMatch(/Add data to your model/)
    expect(studio).toMatch(/PREVIEW/)
    expect(studio).toMatch(/Browse free dataset providers, preview a dataset, then add it to your model/)
  })
})


  it("selects providers from the canonical registry instead of hardcoding one adapter", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/externalProviderId/)
    expect(studio).toMatch(/trainingApi\.searchExternalDatasets\(externalProviderId/)
    expect(studio).toMatch(/Dataset provider/)
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


describe("Model Studio canonical dataset targets", () => {
  it("loads canonical agents, models, Plays and workflows for reference targets", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/agentsApi\.list\(\)/)
    expect(studio).toMatch(/mlModelsApi\.list\(\)/)
    expect(studio).toMatch(/playsApi\.list\(\)/)
    expect(studio).toMatch(/workflowsApi\.list\(\)/)
  })

  it("uses existing target selectors instead of arbitrary ids where canonical lists exist", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/aria-label="Canonical dataset target"/)
    expect(studio).toMatch(/Select an existing target/)
    expect(studio).toMatch(/externalTargetType === "evaluation"/)
    expect(studio).toMatch(/placeholder="Existing evaluation ID"/)
  })

  it("resets a stale target when the target type changes", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/setExternalTargetType/)
    expect(studio).toMatch(/setExternalTargetId\(""\)/)
  })
})


describe("Model Studio user-first dataset picker", () => {
  it("uses task language instead of connector/reference language for primary actions", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/Add data to your model/)
    expect(studio).toMatch(/Search datasets/)
    expect(studio).toMatch(/Use dataset/)
    expect(studio).toMatch(/Upload data/)
  })

  it("defaults Model Studio dataset use to training with a model target", () => {
    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/useState<ExternalDatasetPurpose>\("training"\)/)
    expect(studio).toMatch(/useState<ExternalDatasetTargetType>\("model"\)/)
  })
})
