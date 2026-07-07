import type { UIMessage } from "ai"
import { describe, expect, it } from "vitest"
import { mergeTranscriptWithLiveMessages } from "@/lib/conversation-transcript"
import { uiMessageText } from "@/lib/chat-messages"

function msg(id: string, role: "user" | "assistant", text: string): UIMessage {
  return { id, role, parts: [{ type: "text", text }] }
}

describe("mergeTranscriptWithLiveMessages", () => {
  it("returns live messages when stored transcript is empty", () => {
    const live = [msg("u1", "user", "Hello")]
    expect(mergeTranscriptWithLiveMessages([], live)).toEqual(live)
  })

  it("appends live-only messages without duplicating ids", () => {
    const stored = [msg("u1", "user", "Hello"), msg("a1", "assistant", "Hi")]
    const live = [...stored, msg("u2", "user", "Next")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual(live)
  })

  it("dedupes duplicate trailing user prompts", () => {
    const stored = [msg("u1", "user", "Same prompt")]
    const live = [msg("u1-live", "user", "Same prompt"), msg("a1", "assistant", "Reply")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual([
      msg("u1", "user", "Same prompt"),
      msg("a1", "assistant", "Reply"),
    ])
  })
})

describe("uiMessageText", () => {
  it("reads text parts", () => {
    expect(uiMessageText(msg("u1", "user", "Hello"))).toBe("Hello")
  })

  it("falls back to legacy string content", () => {
    expect(
      uiMessageText({
        id: "legacy",
        role: "user",
        parts: [],
        content: "Legacy prompt",
      } as UIMessage),
    ).toBe("Legacy prompt")
  })
})
