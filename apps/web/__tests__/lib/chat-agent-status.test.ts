import { describe, expect, it } from "vitest"
import {
  deriveAgentStatusLabel,
  shouldHideProgressPanel,
} from "@/lib/chat-agent-status"

describe("deriveAgentStatusLabel", () => {
  it("maps context-phase progress to friendly copy", () => {
    expect(
      deriveAgentStatusLabel({
        progressSteps: [
          "Classifying request (simple)",
          "Checking Apollo, Email",
          "Loading memory and knowledge",
        ],
      }),
    ).toBe("Reviewing context and memory…")
  })

  it("maps running action steps to executing copy", () => {
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
    ).toBe("Gravitre is thinking…")
  })

  it("uses approval-friendly copy when awaiting confirm", () => {
    expect(
      deriveAgentStatusLabel({
        pendingTask: { status: "awaiting_confirm" },
      }),
    ).toBe("Preparing something for your approval…")
  })

  it("falls back to assistant label while streaming", () => {
    expect(
      deriveAgentStatusLabel({
        assistantLabel: "Friendly Assistant",
        isStreaming: true,
      }),
    ).toBe("Friendly Assistant is thinking…")
  })
})

describe("shouldHideProgressPanel", () => {
  it("hides the inline panel for context-only steps", () => {
    expect(
      shouldHideProgressPanel([
        "Classifying request (simple)",
        "Checking Apollo",
        "Loading memory and knowledge",
      ]),
    ).toBe(true)
  })

  it("shows the inline panel when action steps are present", () => {
    expect(
      shouldHideProgressPanel(["Running: Create contact list", "Completed: Search contacts"]),
    ).toBe(false)
  })
})
