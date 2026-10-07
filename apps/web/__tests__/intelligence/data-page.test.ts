import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import {
  computeFit,
  mapFieldToEntity,
  readableTags,
  reportedFields,
  reportedLicense,
  searchTerms,
} from "@/components/intelligence/data/data-match"
import { parseCsv, parseUpload } from "@/components/intelligence/data/parse-upload"

const webRoot = resolve(__dirname, "../..")
const read = (file: string) => readFileSync(resolve(webRoot, file), "utf8")

describe("Intelligence › Data fit ranking", () => {
  it("scores fit from how many search words the metadata contains", () => {
    const terms = searchTerms("Route support tickets to the right queue")
    expect(terms).toEqual(["route", "support", "tickets", "queue"])
    const strong = computeFit(terms, ["customer-support-intents", "Support tickets routed by queue", "routing"])
    expect(strong.level).toBe("strong")
    expect(computeFit(terms, ["support tickets"]).level).toBe("good")
    expect(computeFit(terms, ["weather"]).level).toBe("weak")
  })

  it("turns provider tags into readable labels", () => {
    expect(readableTags(["modality:text", "format:csv", "task_categories:text-classification"])).toEqual(["Text", "Csv"])
  })
})

describe("Intelligence › Data knowledge mapping", () => {
  it("reads Hugging Face feature names and maps them to entity types by name", () => {
    const fields = reportedFields({ dataset_info: { features: [{ name: "customer_name" }, { name: "intent" }] } })
    expect(fields).toEqual(["customer_name", "intent"])
    expect(mapFieldToEntity("customer_name", ["customer", "deal"])).toBe("customer")
    expect(mapFieldToEntity("intent", ["customer", "deal"])).toBeNull()
  })

  it("reports a license only when the provider gives one", () => {
    expect(reportedLicense({ cardData: { license: "mit" } })).toBe("mit")
    expect(reportedLicense({ license: "CC0" })).toBe("CC0")
    expect(reportedLicense({})).toBeNull()
  })
})

describe("Intelligence › Data uploads", () => {
  it("parses CSV examples and rejects rows without both columns", () => {
    expect(parseCsv('input,expected_output\n"a, b",c\n')).toEqual([["input", "expected_output"], ["a, b", "c"]])
    const parsed = parseUpload("x.csv", "input,expected_output\nhello,world\n")
    expect(parsed).toEqual({ kind: "examples", records: [{ input: "hello", expected_output: "world" }] })
    expect(() => parseUpload("x.csv", "input,expected_output\nhello,\n")).toThrow(/Nothing was imported/)
  })

  it("treats prose files as documents", () => {
    expect(parseUpload("policy.md", "# Refunds\nWe refund within 30 days.").kind).toBe("documents")
  })
})

describe("Intelligence › Data page wiring", () => {
  it("uses the design's header, search and sections on real endpoints", () => {
    const page = read("app/intelligence/data/page.tsx")
    expect(page).toMatch(/eyebrow=\{copy\.eyebrow\}/)
    expect(page).toMatch(/Upload a file/)
    expect(page).toMatch(/APP_ROUTES\.connectors/)
    expect(page).toMatch(/<TrainingWorkbench embedded section="datasets"/)
    expect(read("lib/surface-copy.ts")).toMatch(/eyebrow: "Build \/ Data"/)

    const find = read("components/intelligence/data/find-data-section.tsx")
    expect(find).toMatch(/trainingApi\.searchExternalDatasets\(id, term, 12\)/)
    expect(find).toMatch(/trainingApi\.inspectExternalDataset/)
    expect(find).toMatch(/trainingApi\.createExternalDatasetReference/)
    expect(find).toMatch(/Only metadata is read until you import/)
    expect(find).toMatch(/aria-pressed=\{on\}/)
    expect(find).toMatch(/Request access/)

    const yours = read("components/intelligence/data/your-datasets-section.tsx")
    expect(yours).toMatch(/trainingApi\.importFeedback/)
    expect(yours).toMatch(/STARTER_EXAMPLES/)

    const table = read("components/intelligence/data/training-datasets-table.tsx")
    expect(table).toMatch(/m\.datasetId === dataset\.id/)
    expect(table).toMatch(/What each model learned from/)
  })
})
