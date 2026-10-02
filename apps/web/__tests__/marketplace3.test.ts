import { describe, expect, it } from "vitest"
import { certificateLabel, DEPARTMENT_DESIGNS, parseEvidenceIds } from "@/lib/marketplace3"
describe("Marketplace 3 rollout evidence inputs", () => {
  it("covers every first-party department", () => expect(Object.keys(DEPARTMENT_DESIGNS)).toHaveLength(8))
  it("does not imply certification from an unknown label", () => expect(certificateLabel("invented")).toBe("Uncertified"))
  it("deduplicates stored references and accepts line or comma separation", () => {
    const a = "00000000-0000-0000-0000-000000000001", b = "00000000-0000-0000-0000-000000000002"
    expect(parseEvidenceIds(`${a},\n${b}\n${a}`)).toEqual([a,b])
  })
  it("rejects self-attested evidence and arbitrary JSON", () => expect(() => parseEvidenceIds('{"verified":true}')).toThrow())
  it("does not invent evidence when inputs are empty", () => expect(parseEvidenceIds("")).toEqual([]))
})
