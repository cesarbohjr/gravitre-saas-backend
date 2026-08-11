import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { KnowledgeCitationCard } from "@/components/intelligence/knowledge-citation-card"

describe("KnowledgeCitationCard honesty", () => {
  it("surfaces curated_summary_live_html_blocked distinctly", () => {
    render(
      <KnowledgeCitationCard
        citations={[
          {
            citation: "CISA — https://www.cisa.gov/stopransomware",
            authority_score: 0.95,
            jurisdiction: "US-federal",
            license_type: "A",
            content_mode: "curated_summary_live_html_blocked",
            fetch_status: { html_blocked: true, attempted: true },
          },
        ]}
      />,
    )
    expect(
      screen.getByText("Curated summary — live source fetch was blocked"),
    ).toBeInTheDocument()
  })

  it("does not show curated label for live-looking citations without content_mode", () => {
    render(
      <KnowledgeCitationCard
        citations={[
          {
            citation: "NIST CSF 2.0",
            authority_score: 0.97,
            jurisdiction: "US",
            license_type: "A",
          },
        ]}
      />,
    )
    expect(screen.queryByText(/Curated summary/i)).not.toBeInTheDocument()
  })
})
