import { describe, expect, it } from "vitest"
import { describeStatus, STATUS_LANGUAGE, TONE_BADGE_CLASS } from "@/lib/intelligence/status-language"

describe("status-language (Phase 2.5 — honest status translation)", () => {
  it("never returns a bare word without a detail sentence for every mapped status", () => {
    for (const [key, entry] of Object.entries(STATUS_LANGUAGE)) {
      expect(entry.phrase.length, `phrase for "${key}"`).toBeGreaterThan(0)
      if (key !== "unknown") {
        expect(entry.detail.length, `detail for "${key}"`).toBeGreaterThan(0)
      }
      expect(TONE_BADGE_CLASS[entry.tone]).toBeDefined()
    }
  })

  it("matches the master brief's exact 8-row translation table", () => {
    expect(describeStatus("untrained").phrase).toBe("Needs training")
    expect(describeStatus("training").phrase).toBe("Learning from your data")
    expect(describeStatus("trained").phrase).toBe("Ready to use")
    expect(describeStatus("deployed").phrase).toBe("Actively predicting")
    expect(describeStatus("evaluating").phrase).toBe("Checking performance")
    expect(describeStatus("stale").phrase).toBe("Needs updating")
    expect(describeStatus("failed").phrase).toBe("Training needs attention")
    expect(describeStatus("fine_tuning").phrase).toBe("Improving with new examples")
  })

  it("is case- and whitespace-insensitive on real API status strings", () => {
    expect(describeStatus(" TRAINED ").phrase).toBe("Ready to use")
    expect(describeStatus("Heuristic").phrase).toBe("Estimating with rules")
  })

  it("never fabricates a friendly phrase for a genuinely unmapped status — humanizes and discloses the gap", () => {
    const result = describeStatus("some_new_status_nobody_mapped_yet")
    expect(result.phrase).toBe("Some New Status Nobody Mapped Yet")
    expect(result.detail).toContain("No business-language mapping exists yet")
  })

  it("falls back honestly for null/undefined/empty status", () => {
    expect(describeStatus(null).phrase).toBe("Status unknown")
    expect(describeStatus(undefined).phrase).toBe("Status unknown")
    expect(describeStatus("").phrase).toBe("Status unknown")
  })
})
