import { describe, expect, it } from "vitest"
import {
  deriveAgentStatusLabel,
  shouldHideProgressPanel,
} from "@/lib/chat-agent-status"

describe("deriveAgentStatusLabel", () => {
  it("uses the current context-phase step as specific copy", () => {
    expect(
      deriveAgentStatusLabel({
        progressSteps: [
          "Classifying request (simple)",
          "Checking Apollo, Email",
          "Loading memory and knowledge",
        ],
      }),
    ).toBe("Loading memory and knowledge…")
  })

  it("maps running action steps to the real current step", () => {
    expect(
      deriveAgentStatusLabel({
        progressSteps: ["Completed: Search contacts", "Running: Create contact list"],
      }),
    ).toBe("Create contact list…")
  })

  it("never surfaces raw internal codes", () => {
    expect(
      deriveAgentStatusLabel({
        answerExplanation: "write_approval_required",
        isBusy: true,
      }),
    ).toBe("Working on it…")
  })

  it("uses approval-friendly copy when awaiting confirm", () => {
    expect(
      deriveAgentStatusLabel({
        pendingTask: { status: "awaiting_confirm" },
      }),
    ).toBe("Preparing something for your approval…")
  })

  it("fails closed while streaming with no mapped activity", () => {
    expect(
      deriveAgentStatusLabel({
        assistantLabel: "Friendly Assistant",
        isStreaming: true,
      }),
    ).toBe("Working on it…")
  })

  it("prefers userStatus over a raw explanation", () => {
    expect(
      deriveAgentStatusLabel({
        answerExplanation: "CognitiveTurnKernel pre-ACT complete",
        userStatusLabel: "Reviewing context and memory",
      }),
    ).toBe("Reviewing context and memory…")
  })
})

describe("shouldHideProgressPanel", () => {
  it("shows the inline checklist for context-only multi-step work", () => {
    expect(
      shouldHideProgressPanel([
        "Classifying request (simple)",
        "Checking Apollo",
        "Loading memory and knowledge",
      ]),
    ).toBe(false)
  })

  it("shows the inline panel when action steps are present", () => {
    expect(
      shouldHideProgressPanel(["Running: Create contact list", "Completed: Search contacts"]),
    ).toBe(false)
  })

  it("hides the panel when there is only one named step", () => {
    expect(shouldHideProgressPanel(["Running: Search contacts"])).toBe(true)
  })
})
