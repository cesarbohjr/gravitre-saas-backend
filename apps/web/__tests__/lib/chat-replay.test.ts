import { describe, expect, it } from "vitest"
import { applyChatReplay, isUserChatAbort } from "@/lib/chat-replay"
import type { UIMessage } from "ai"

describe("applyChatReplay", () => {
  it("fills an empty trailing assistant bubble from a completed turn", () => {
    const messages: UIMessage[] = [
      { id: "u1", role: "user", parts: [{ type: "text", text: "hi" }] },
      { id: "a1", role: "assistant", parts: [{ type: "text", text: "" }] },
    ]
    const next = applyChatReplay(messages, {
      ok: true,
      event_id: "evt-9",
      conversation_id: "conv-1",
      assistant_message_id: "evt-9",
      user_text: "hi",
      assistant_text: "Here are three contacts.",
    })
    expect(next[next.length - 1]?.id).toBe("evt-9")
    const parts = next[next.length - 1]?.parts ?? []
    const text = parts.map((part) => ("text" in part ? String(part.text || "") : "")).join("")
    expect(text).toContain("Here are three contacts.")
  })

  it("ignores a replay that answers a different prompt", () => {
    const messages: UIMessage[] = [
      { id: "u0", role: "user", parts: [{ type: "text", text: "list my deals" }] },
      { id: "a0", role: "assistant", parts: [{ type: "text", text: "You have 3 deals." }] },
      { id: "u1", role: "user", parts: [{ type: "text", text: "email Sarah the deck" }] },
    ]
    const next = applyChatReplay(messages, {
      ok: true,
      event_id: "evt-old",
      user_text: "list my deals",
      assistant_text: "You have 3 deals.",
    })
    expect(next).toBe(messages)
  })

  it("does not overwrite an assistant bubble that already has prose", () => {
    const messages: UIMessage[] = [
      { id: "a1", role: "assistant", parts: [{ type: "text", text: "Already here." }] },
    ]
    const next = applyChatReplay(messages, {
      ok: true,
      assistant_text: "Replay should not win",
    })
    expect(next).toBe(messages)
  })
})

describe("isUserChatAbort", () => {
  it("treats AbortError as a user stop", () => {
    const error = new Error("The user aborted a request.")
    error.name = "AbortError"
    expect(isUserChatAbort(error)).toBe(true)
    expect(isUserChatAbort(new Error("AI assistant is currently unavailable"))).toBe(false)
  })
})
