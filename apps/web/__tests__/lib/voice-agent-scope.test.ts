import { describe, expect, it } from "vitest"

import { CHAT_PERSONA_OPTIONS } from "@/lib/chat-personas"
import { normalizeAgentResponseStyle, readResponseStyleFromConfig } from "@/lib/agent-response-style"
import { resolveVoiceAgentId, showVoiceAgentPicker } from "@/lib/voice-agent-scope"

describe("resolveVoiceAgentId", () => {
  it("uses the scoped chat agent even when the picker chose another agent", () => {
    expect(resolveVoiceAgentId({ scopedAgentId: "agent-a", pickedAgentId: "agent-b" })).toBe("agent-a")
  })

  it("uses the scoped agent when the picker has no voice-ready pick", () => {
    expect(resolveVoiceAgentId({ scopedAgentId: "agent-a", pickedAgentId: null })).toBe("agent-a")
  })

  it("falls back to the picker pick when unscoped", () => {
    expect(resolveVoiceAgentId({ scopedAgentId: null, pickedAgentId: "agent-b" })).toBe("agent-b")
  })

  it("returns undefined (default assistant voice) when nothing is selected", () => {
    expect(resolveVoiceAgentId({ scopedAgentId: "  ", pickedAgentId: "" })).toBeUndefined()
  })

  it("hides the voice picker only on scoped chats", () => {
    expect(showVoiceAgentPicker("agent-a")).toBe(false)
    expect(showVoiceAgentPicker(null)).toBe(true)
  })
})

describe("response style catalog", () => {
  it("matches the backend RESPONSE_STYLE_CRITERIA keys", () => {
    expect(CHAT_PERSONA_OPTIONS.map((option) => option.key).sort()).toEqual(
      [
        "deep_research_analyst",
        "engineering_copilot",
        "executive_strategist",
        "finance_analyst",
        "friendly_assistant",
        "hr_advisor",
        "marketing_operator",
        "operations_analyst",
        "sales_advisor",
        "support_specialist",
      ].sort(),
    )
  })

  it("has unique labels and tones", () => {
    const labels = CHAT_PERSONA_OPTIONS.map((option) => option.label)
    const tones = CHAT_PERSONA_OPTIONS.map((option) => option.tone)
    expect(new Set(labels).size).toBe(labels.length)
    expect(new Set(tones).size).toBe(tones.length)
  })

  it("keeps hr_advisor as a valid agent response style", () => {
    expect(normalizeAgentResponseStyle("hr_advisor")).toBe("hr_advisor")
    expect(readResponseStyleFromConfig({ response_style: "hr_advisor" })).toBe("hr_advisor")
  })
})
