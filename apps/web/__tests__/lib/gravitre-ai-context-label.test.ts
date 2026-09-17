import { describe, expect, it } from "vitest"
import {
  formatGravitreAiContextLabel,
  gravitreAiContextHasVisibleState,
  gravitreHelperStatusCopy,
} from "@/lib/gravitre-ai-context-label"

describe("formatGravitreAiContextLabel", () => {
  it("formats agent and selection independently", () => {
    const label = formatGravitreAiContextLabel({
      agentName: "Lead Triage",
      selectedKind: "entity",
      selectedLabel: "Acme Corporation",
    })
    expect(label.agentLine).toBe("Talking with Lead Triage")
    expect(label.selectionLine).toBe("Using entity: Acme Corporation")
    expect(gravitreAiContextHasVisibleState(label)).toBe(true)
  })

  it("is empty when there is no agent or selection", () => {
    const label = formatGravitreAiContextLabel({})
    expect(gravitreAiContextHasVisibleState(label)).toBe(false)
  })

  it("lets live helper presence override object context", () => {
    const context = formatGravitreAiContextLabel({
      selectedKind: "entity",
      selectedLabel: "Acme",
    })
    expect(gravitreHelperStatusCopy("listening", "Listening", context)).toBe("Listening")
    expect(gravitreHelperStatusCopy("ready", "Ready", context)).toBe("Using entity: Acme")
  })
})
