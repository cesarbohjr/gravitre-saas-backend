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

  it("keeps live user when stored is empty during in-flight send", () => {
    const live = [msg("u-live", "user", "tell me about the best CRM"), msg("a1", "assistant", "")]
    expect(mergeTranscriptWithLiveMessages([], live)).toEqual(live)
  })

  it("dedupes a whole duplicated turn, not just the user prompt", () => {
    // The reported defect. Live ids are client-generated, stored ids are DB
    // uuids, so the same turn arrives twice under different ids and rendered as
    // user, assistant, user, assistant.
    const stored = [msg("db-u1", "user", "hi"), msg("db-a1", "assistant", "Hey — I'm here.")]
    const live = [msg("live-u1", "user", "hi"), msg("live-a1", "assistant", "Hey — I'm here.")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual(stored)
  })

  it("collapses a duplicated turn while still appending what is genuinely new", () => {
    const stored = [msg("db-u1", "user", "hi"), msg("db-a1", "assistant", "Hey")]
    const live = [
      msg("live-u1", "user", "hi"),
      msg("live-a1", "assistant", "Hey"),
      msg("live-u2", "user", "what can you do?"),
    ]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual([
      ...stored,
      msg("live-u2", "user", "what can you do?"),
    ])
  })

  it("dedupes a duplicated multi-turn tail", () => {
    const stored = [
      msg("db-u1", "user", "first"),
      msg("db-a1", "assistant", "one"),
      msg("db-u2", "user", "second"),
      msg("db-a2", "assistant", "two"),
    ]
    const live = [
      msg("live-u1", "user", "first"),
      msg("live-a1", "assistant", "one"),
      msg("live-u2", "user", "second"),
      msg("live-a2", "assistant", "two"),
    ]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual(stored)
  })

  it("keeps a genuine repeat when the assistant reply differs", () => {
    // Asking the same thing twice is legitimate and must not be swallowed.
    const stored = [msg("db-u1", "user", "status?"), msg("db-a1", "assistant", "All good")]
    const live = [msg("live-u2", "user", "status?"), msg("live-a2", "assistant", "")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual([...stored, ...live])
  })

  it("does not collapse a turn whose assistant reply differs", () => {
    // Documents the boundary: the overlap has to be anchored at the tail of
    // stored, so a same-prompt/different-reply pair (a regenerate) does not
    // match and both copies survive. Matching a non-contiguous run would mean
    // reordering the thread, which is out of scope here.
    const stored = [msg("db-u1", "user", "hi"), msg("db-a1", "assistant", "Hey")]
    const live = [msg("live-u1", "user", "hi"), msg("live-a1", "assistant", "Hello there")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual([...stored, ...live])
  })

  it("ignores whitespace differences between the two copies", () => {
    const stored = [msg("db-u1", "user", "hi"), msg("db-a1", "assistant", "Hey")]
    const live = [msg("live-u1", "user", " hi "), msg("live-a1", "assistant", "Hey\n")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual(stored)
  })

  it("still matches on id when ids agree", () => {
    const stored = [msg("u1", "user", "hi"), msg("a1", "assistant", "Hey")]
    expect(mergeTranscriptWithLiveMessages(stored, stored)).toEqual(stored)
  })

  it("leaves an unrelated live tail completely alone", () => {
    const stored = [msg("db-u1", "user", "hi"), msg("db-a1", "assistant", "Hey")]
    const live = [msg("live-u2", "user", "different question")]
    expect(mergeTranscriptWithLiveMessages(stored, live)).toEqual([...stored, ...live])
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
