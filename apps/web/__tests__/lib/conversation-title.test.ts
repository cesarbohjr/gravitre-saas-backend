import { describe, expect, it } from "vitest"
import {
  deriveConversationTitle,
  jaccardSimilarity,
  shouldRefreshConversationTitle,
  tokenizeConversationTitle,
} from "@/lib/conversation-title"

describe("STA-308 conversation title refresh", () => {
  it("derives a truncated title from the prompt", () => {
    expect(deriveConversationTitle("  Search MSPs in Apollo  ")).toBe(
      "Search MSPs in Apollo",
    )
    const long = "x".repeat(100)
    expect(deriveConversationTitle(long).length).toBe(80)
    expect(deriveConversationTitle(long).endsWith("…")).toBe(true)
  })

  it("refreshes when Apollo search becomes HubSpot/Slack orchestration (STA-307 repro)", () => {
    expect(
      shouldRefreshConversationTitle(
        "Search MSPs in Apollo",
        "Create a HubSpot contact for Acme and post a Slack update in #sales",
      ),
    ).toBe(true)
  })

  it("does not refresh on confirm-via-chat affirmations", () => {
    expect(shouldRefreshConversationTitle("Search MSPs in Apollo", "yes")).toBe(
      false,
    )
    expect(
      shouldRefreshConversationTitle("Search MSPs in Apollo", "go ahead"),
    ).toBe(false)
  })

  it("does not refresh on soft follow-ups / continuations", () => {
    expect(
      shouldRefreshConversationTitle(
        "Search MSPs in Apollo",
        "also filter by enterprise size",
      ),
    ).toBe(false)
    expect(
      shouldRefreshConversationTitle(
        "Search MSPs in Apollo",
        "actually make that SaaS only",
      ),
    ).toBe(false)
  })

  it("does not refresh when the ask is still the same task", () => {
    expect(
      shouldRefreshConversationTitle(
        "Search MSPs in Apollo",
        "Search MSPs in Apollo for California",
      ),
    ).toBe(false)
  })

  it("token Jaccard stays high for near-duplicate titles", () => {
    const a = tokenizeConversationTitle("Search MSPs in Apollo")
    const b = tokenizeConversationTitle("Search MSPs in Apollo for California")
    expect(jaccardSimilarity(a, b)).toBeGreaterThan(0.35)
  })
})
