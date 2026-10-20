import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import { roiMetricDisplay } from "@/lib/intelligence/performance-display"

const webRoot = resolve(__dirname, "../..")
const source = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

describe("backend/frontend reconciliation regression guards", () => {
  it("does not mislabel a soft-deleted source as disconnected or permanently purged", () => {
    const page = source("app/(app)/sources/[id]/page.tsx")
    expect(page).toContain("excludes its documents from retrieval")
    expect(page).toContain("does not confirm permanent deletion")
    expect(page).not.toContain("This will disconnect {name} from Gravitre")
    expect(page).toContain('key.startsWith("intelligence/")')
  })

  it("revalidates run, agent and session views after approval decisions", () => {
    const page = source("app/(app)/approvals/page.tsx")
    expect(page).toContain('key.startsWith("/api/runs")')
    expect(page).toContain('key.startsWith("/api/agents")')
    expect(page).toContain('key.startsWith("/api/sessions")')
    expect(page).toContain('key.startsWith("agent-identity-")')
    expect(page).toContain("mutateCache(")
  })

  it("preserves measured and estimated ROI distinctions", () => {
    expect(roiMetricDisplay({ label: "Hours saved", value: 2, unit: "hours", provenance: "measured" }).hint).toBe("Measured")
    expect(roiMetricDisplay({ label: "Hours saved", value: 2, unit: "hours", provenance: "estimate" }).hint).toContain("Estimate")
    expect(roiMetricDisplay({ label: "Hours saved", value: null, unit: "hours", provenance: "insufficient_data" }).unknown).toBe(true)
  })
})
