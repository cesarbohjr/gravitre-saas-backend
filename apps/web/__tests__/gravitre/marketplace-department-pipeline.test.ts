import { describe, expect, it } from "vitest"
import { pipelineDepartmentKey } from "@/lib/marketplace-department-pipeline"

describe("pipelineDepartmentKey", () => {
  it("maps seed pack departments onto pipeline catalog keys", () => {
    expect(pipelineDepartmentKey("Marketing")).toBe("marketing")
    expect(pipelineDepartmentKey("Revenue Operations")).toBe("sales")
    expect(pipelineDepartmentKey("HR")).toBe("hr")
    expect(pipelineDepartmentKey("Operations")).toBe("msp")
    expect(pipelineDepartmentKey("Finance")).toBe("finance")
  })

  it("leaves departments without a pipeline unmapped", () => {
    expect(pipelineDepartmentKey("Customer Success")).toBeNull()
    expect(pipelineDepartmentKey("Support")).toBeNull()
    expect(pipelineDepartmentKey("general")).toBeNull()
    expect(pipelineDepartmentKey("")).toBeNull()
  })
})
