import { describe, expect, it } from "vitest"
import {
  isAuthoritativeMissingConversationError,
  shouldVerifyMissingConversation,
} from "@/lib/active-conversation-recovery"
import { ApiError } from "@/lib/fetcher"

describe("shouldVerifyMissingConversation", () => {
  it("returns true when active conversation is missing from loaded list and chat is idle", () => {
    expect(
      shouldVerifyMissingConversation({
        orgReady: true,
        activeConversationId: "conv-1",
        conversationsLoading: false,
        hasConversationInList: false,
        hasPendingConversation: false,
        isSessionBusy: false,
        chatStatus: "ready",
      }),
    ).toBe(true)
  })

  it("returns false while conversations are loading", () => {
    expect(
      shouldVerifyMissingConversation({
        orgReady: true,
        activeConversationId: "conv-1",
        conversationsLoading: true,
        hasConversationInList: false,
        hasPendingConversation: false,
        isSessionBusy: false,
        chatStatus: "ready",
      }),
    ).toBe(false)
  })

  it("returns false while a pending or streaming turn exists", () => {
    expect(
      shouldVerifyMissingConversation({
        orgReady: true,
        activeConversationId: "conv-1",
        conversationsLoading: false,
        hasConversationInList: false,
        hasPendingConversation: true,
        isSessionBusy: false,
        chatStatus: "ready",
      }),
    ).toBe(false)

    expect(
      shouldVerifyMissingConversation({
        orgReady: true,
        activeConversationId: "conv-1",
        conversationsLoading: false,
        hasConversationInList: false,
        hasPendingConversation: false,
        isSessionBusy: false,
        chatStatus: "streaming",
      }),
    ).toBe(false)
  })
})

describe("isAuthoritativeMissingConversationError", () => {
  it("accepts 403 and 404 ApiError statuses only", () => {
    expect(isAuthoritativeMissingConversationError(new ApiError("forbidden", 403))).toBe(true)
    expect(isAuthoritativeMissingConversationError(new ApiError("missing", 404))).toBe(true)
    expect(isAuthoritativeMissingConversationError(new ApiError("timeout", 503))).toBe(false)
    expect(isAuthoritativeMissingConversationError(new Error("boom"))).toBe(false)
  })
})
