import { describe, expect, it } from "vitest"
import {
  SAFE_STATUS_FALLBACK,
  looksLikeInternalStatus,
  sanitizeUserActivityLabel,
  specificToolStatus,
} from "@/lib/ai-state-matrix"
import { deriveAgentStatusLabel } from "@/lib/chat-agent-status"

const MUTATION_UNMAPPED = "TotallyNewUnmappedKernel.info"

describe("AI State matrix sanitizer", () => {
  it("maps the reported kernel leak to human copy", () => {
    expect(sanitizeUserActivityLabel("CognitiveTurnKernel pre-ACT complete")).toBe(
      "Reviewing context and memory",
    )
  })

  it("fails closed on a deliberately unmapped internal state (mutation)", () => {
    expect(looksLikeInternalStatus(MUTATION_UNMAPPED)).toBe(true)
    expect(sanitizeUserActivityLabel(MUTATION_UNMAPPED)).toBe(SAFE_STATUS_FALLBACK)
    expect(
      deriveAgentStatusLabel({
        answerExplanation: MUTATION_UNMAPPED,
        isBusy: true,
      }),
    ).toBe("Working on it…")
  })

  it("never returns snake_case or logger-shaped copy", () => {
    expect(deriveAgentStatusLabel({ answerExplanation: "write_approval_required" })).toBe(
      "Working on it…",
    )
    expect(deriveAgentStatusLabel({ answerExplanation: "kernel.info" })).toBe("Working on it…")
  })

  it("keeps specific truthful tool copy", () => {
    expect(specificToolStatus("searchKnowledgeBase")).toBe("Searching your knowledge base")
    expect(specificToolStatus("hubspot.contacts.search")).toBe("Searching your Hubspot contacts")
  })
})
