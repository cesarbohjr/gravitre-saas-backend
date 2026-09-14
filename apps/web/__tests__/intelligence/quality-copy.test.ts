import { describe, expect, it } from "vitest"
import { formatQualityFlagsHuman, qualityFlagToCopy } from "@/lib/intelligence/quality-copy"

describe("quality-copy", () => {
  it("maps machine flags to human copy", () => {
    expect(qualityFlagToCopy("INSUFFICIENT_DATA")).toBe("Not enough verified data yet")
    expect(qualityFlagToCopy("NOT_CONFIGURED")).toBe("Not set up yet")
  })

  it("dedupes formatted flags", () => {
    expect(formatQualityFlagsHuman(["INSUFFICIENT_DATA", "insufficient_data"])).toEqual([
      "Not enough verified data yet",
    ])
  })
})
