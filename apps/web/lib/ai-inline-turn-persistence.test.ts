import { describe, expect, it } from "vitest"
import {
  INLINE_TURN_TOOL_NAME,
  serializeInlineTurn,
  splitConversationMessages,
} from "@/lib/ai-inline-turn-persistence"

describe("splitConversationMessages", () => {
  it("separates chat messages from persisted inline execute turns", () => {
    const inlineTurn = {
      id: "turn-1",
      prompt: "Analyze pipeline",
      engine: "execute" as const,
      status: "completed" as const,
      executePlan: null,
    }
    const rows = serializeInlineTurn(inlineTurn).map((row, index) => ({
      ...row,
      id: index === 0 ? "msg-user" : "msg-assistant",
      conversation_id: "conv-1",
    }))

    const { chatMessages, inlineTurns } = splitConversationMessages(rows)
    expect(chatMessages).toHaveLength(0)
    expect(inlineTurns).toHaveLength(1)
    expect(inlineTurns[0]?.prompt).toBe("Analyze pipeline")
  })

  it("keeps regular chat turns in chatMessages", () => {
    const { chatMessages, inlineTurns } = splitConversationMessages([
      {
        id: "1",
        conversation_id: "conv-1",
        role: "user",
        content: "Hello",
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: "2",
        conversation_id: "conv-1",
        role: "assistant",
        content: "Hi there",
        created_at: "2026-01-01T00:00:01Z",
      },
    ])

    expect(chatMessages).toHaveLength(2)
    expect(inlineTurns).toHaveLength(0)
  })

  it("recognizes inline turn marker in tool_calls", () => {
    expect(INLINE_TURN_TOOL_NAME).toBe("gravitre.inline_turn")
  })
})
