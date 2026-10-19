import { describe, expect, it } from "vitest"
import {
  changeCopy,
  costShares,
  formatMultiple,
  healthBand,
  ingestBars,
  isValidDomain,
  parsePositiveNumber,
  recommendationLevel,
  resolveEnterpriseSection,
  sourceStatusMeta,
} from "@/lib/settings-api/enterprise"

describe("enterprise settings helpers", () => {
  it("resolves ?section= and keeps old ?tab= deep links working", () => {
    expect(resolveEnterpriseSection("agent-roi", null)).toBe("agent-roi")
    expect(resolveEnterpriseSection(null, "cs")).toBe("command-center")
    expect(resolveEnterpriseSection(null, "branding")).toBe("white-label")
    expect(resolveEnterpriseSection("nope", "nope")).toBe("command-center")
  })

  it("maps backend grades to the design's bands", () => {
    expect(healthBand("healthy").label).toBe("Healthy")
    expect(healthBand("at_risk").label).toBe("Watch")
    expect(healthBand("critical")).toEqual({ label: "Critical", tone: "red" })
  })

  it("levels recommendations from the real suggestion priority", () => {
    expect(recommendationLevel(90).label).toBe("HIGH")
    expect(recommendationLevel(80).label).toBe("MEDIUM")
    expect(recommendationLevel(65).label).toBe("LOW")
  })

  it("gives zero ingest days a red stub and scales the rest", () => {
    const bars = ingestBars([
      { date: "2026-10-18", documents: 0 },
      { date: "2026-10-19", documents: 50 },
      { date: "2026-10-20", documents: 100 },
    ])
    expect(bars.map((b) => [b.zero, b.heightPct])).toEqual([
      [true, 3],
      [false, 50],
      [false, 100],
    ])
    expect(ingestBars([{ date: "x", documents: 0 }])[0].heightPct).toBe(3)
  })

  it("picks row actions from source status", () => {
    expect(sourceStatusMeta("failed").cta).toBe("Retry")
    expect(sourceStatusMeta("paused").cta).toBe("Resume")
    expect(sourceStatusMeta("healthy").cta).toBe("Sync now")
    expect(sourceStatusMeta("syncing").cta).toBeNull()
    expect(sourceStatusMeta("not_configured").label).toBe("Not set up")
  })

  it("describes the change against the previous period only when there is one", () => {
    expect(changeCopy(null, 7)).toBeNull()
    expect(changeCopy(12, 7)).toEqual({ text: "12% more than last week", tone: "green" })
    expect(changeCopy(-5, 30)?.text).toBe("5% fewer than the 30 days before")
  })

  it("computes shares and multiples", () => {
    expect(costShares([{ costUsd: 1 }, { costUsd: 3 }], 4).map((r) => r.sharePct)).toEqual([25, 75])
    expect(costShares([{ costUsd: 0 }], 0)[0].sharePct).toBe(0)
    expect(formatMultiple(120)).toBe("120×")
    expect(formatMultiple(2.345)).toBe("2.3×")
    expect(formatMultiple(null)).toBeNull()
  })

  it("validates numeric inputs and domains", () => {
    expect(parsePositiveNumber("45", 1000)).toBe(45)
    expect(parsePositiveNumber("", 1000)).toBeNull()
    expect(parsePositiveNumber("-3", 1000)).toBeNull()
    expect(parsePositiveNumber("2000", 1440)).toBeNull()
    expect(isValidDomain("ai.yourcompany.com")).toBe(true)
    expect(isValidDomain("")).toBe(true)
    expect(isValidDomain("https://x.com")).toBe(false)
    expect(isValidDomain("nodot")).toBe(false)
  })
})
