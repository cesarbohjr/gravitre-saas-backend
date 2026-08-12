import { describe, expect, it } from "vitest"
import { contentModeHonestyLabel } from "@/components/intelligence/knowledge-citation-card"

describe("KnowledgeCitationCard honesty", () => {
  it("surfaces curated_summary_live_html_blocked distinctly", () => {
    expect(contentModeHonestyLabel("curated_summary_live_html_blocked")).toBe(
      "Curated summary — live source fetch was blocked",
    )
  })

  it("does not show curated label for live-looking citations without content_mode", () => {
    expect(contentModeHonestyLabel(undefined)).toBeNull()
    expect(contentModeHonestyLabel("live_html")).toBeNull()
  })
})
