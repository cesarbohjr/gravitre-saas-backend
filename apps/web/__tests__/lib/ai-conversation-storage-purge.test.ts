// @vitest-environment jsdom
/**
 * Logout must not leave the previous user's conversation on the machine.
 *
 * `clearCachedConversationMessages` only ever clears one known conversation id,
 * which is not enough at logout: caches accumulate one entry per conversation the
 * user visited, and by then we no longer know which ids those were.
 */
import { beforeEach, describe, expect, it } from "vitest"
import {
  AI_CONVERSATION_ID_KEY,
  purgeStoredConversationState,
  readCachedConversationMessages,
  readCachedInlineTurns,
  readStoredConversationId,
  writeCachedConversationMessages,
  writeCachedInlineTurns,
  writeStoredConversationId,
} from "@/lib/ai-conversation-storage"

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe("purgeStoredConversationState", () => {
  it("removes the active thread id from localStorage", () => {
    writeStoredConversationId("conv-1")
    expect(readStoredConversationId()).toBe("conv-1")
    purgeStoredConversationState()
    expect(readStoredConversationId()).toBeNull()
    expect(localStorage.getItem(AI_CONVERSATION_ID_KEY)).toBeNull()
  })

  it("removes cached messages and inline turns", () => {
    writeCachedConversationMessages("conv-1", [
      { id: "m1", role: "user", parts: [{ type: "text", text: "private thing" }] },
    ] as never)
    writeCachedInlineTurns("conv-1", [{ id: "t1" }])
    expect(readCachedConversationMessages("conv-1")).not.toBeNull()
    expect(readCachedInlineTurns("conv-1")).not.toBeNull()

    purgeStoredConversationState()

    expect(readCachedConversationMessages("conv-1")).toBeNull()
    expect(readCachedInlineTurns("conv-1")).toBeNull()
  })

  it("removes caches for every conversation, not just the active one", () => {
    // The regression that motivated a prefix scan. At logout we no longer know
    // which ids the user visited, so a per-id clear leaves the rest behind.
    for (const id of ["conv-1", "conv-2", "conv-3"]) {
      writeCachedConversationMessages(id, [
        { id: `m-${id}`, role: "user", parts: [{ type: "text", text: id }] },
      ] as never)
    }
    writeStoredConversationId("conv-3")

    purgeStoredConversationState()

    for (const id of ["conv-1", "conv-2", "conv-3"]) {
      expect(readCachedConversationMessages(id)).toBeNull()
    }
  })

  it("removes surface handoff payloads, which can hold a typed prompt", () => {
    sessionStorage.setItem("gravitre-ai-handoff:chat", JSON.stringify({ prompt: "confidential" }))
    purgeStoredConversationState()
    expect(sessionStorage.getItem("gravitre-ai-handoff:chat")).toBeNull()
  })

  it("removes the legacy conversation id key too", () => {
    localStorage.setItem("gravitre_last_conversation_id", "old-conv")
    purgeStoredConversationState()
    expect(localStorage.getItem("gravitre_last_conversation_id")).toBeNull()
  })

  it("leaves presentation preferences alone", () => {
    // Scoping proof: the purge targets conversation content, not unrelated UI
    // preferences, so logging out does not reset the operator's theme choices.
    localStorage.setItem("gravitre-chat-background", "aurora")
    sessionStorage.setItem("gravitre-ai-float-geometry", '{"w":420}')
    purgeStoredConversationState()
    expect(localStorage.getItem("gravitre-chat-background")).toBe("aurora")
    expect(sessionStorage.getItem("gravitre-ai-float-geometry")).toBe('{"w":420}')
  })

  it("does not throw when there is nothing to purge", () => {
    expect(() => purgeStoredConversationState()).not.toThrow()
  })
})
