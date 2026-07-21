import { describe, expect, it } from "vitest"
import {
  formatMessageExactTime,
  formatMessageRelativeTime,
  messageCreatedAt,
  shouldShowClusterTimestamp,
} from "@/lib/chat-message-time"
import { groupConversationsByRecency } from "@/lib/conversation-history-groups"
import type { Conversation } from "@/types/api"

describe("chat-message-time", () => {
  it("reads created_at from message metadata", () => {
    expect(messageCreatedAt({ metadata: { created_at: "2026-07-20T12:00:00.000Z" } })).toBe(
      "2026-07-20T12:00:00.000Z",
    )
    expect(messageCreatedAt({ metadata: {} })).toBeNull()
  })

  it("formats recent relative times", () => {
    const now = Date.parse("2026-07-20T12:30:00.000Z")
    expect(formatMessageRelativeTime("2026-07-20T12:29:30.000Z", now)).toBe("just now")
    expect(formatMessageRelativeTime("2026-07-20T12:25:00.000Z", now)).toBe("5m ago")
    expect(formatMessageRelativeTime("2026-07-20T10:30:00.000Z", now)).toBe("2h ago")
  })

  it("exposes an exact timestamp string", () => {
    const exact = formatMessageExactTime("2026-07-20T12:00:00.000Z")
    expect(exact.length).toBeGreaterThan(10)
  })

  it("clusters consecutive same-role messages within 2 minutes", () => {
    const messages = [
      { id: "1", role: "user", metadata: { created_at: "2026-07-20T12:00:00.000Z" } },
      { id: "2", role: "user", metadata: { created_at: "2026-07-20T12:00:30.000Z" } },
      { id: "3", role: "assistant", metadata: { created_at: "2026-07-20T12:01:00.000Z" } },
    ]
    expect(shouldShowClusterTimestamp(messages, 0)).toBe(true)
    expect(shouldShowClusterTimestamp(messages, 1)).toBe(false)
    expect(shouldShowClusterTimestamp(messages, 2)).toBe(true)
  })
})

describe("groupConversationsByRecency", () => {
  const base = (partial: Partial<Conversation> & Pick<Conversation, "id" | "updated_at">): Conversation => ({
    title: partial.title || partial.id,
    created_at: partial.updated_at,
    message_count: 1,
    ...partial,
  })

  it("buckets by recency and keeps pinned first without re-sorting within buckets", () => {
    const now = Date.parse("2026-07-20T15:00:00.000Z")
    const rows = [
      base({ id: "pinned", updated_at: "2026-07-01T00:00:00.000Z", pinned_at: "2026-07-20T14:00:00.000Z" }),
      base({ id: "today-a", updated_at: "2026-07-20T14:00:00.000Z" }),
      base({ id: "today-b", updated_at: "2026-07-20T13:00:00.000Z" }),
      base({ id: "yesterday", updated_at: "2026-07-19T12:00:00.000Z" }),
      base({ id: "week", updated_at: "2026-07-15T12:00:00.000Z" }),
      base({ id: "month", updated_at: "2026-07-01T12:00:00.000Z" }),
      base({ id: "older", updated_at: "2026-05-01T12:00:00.000Z" }),
    ]
    const groups = groupConversationsByRecency(rows, now)
    expect(groups.map((g) => g.label)).toEqual([
      "Pinned",
      "Today",
      "Yesterday",
      "Previous 7 Days",
      "Previous 30 Days",
      "May",
    ])
    expect(groups[1].conversations.map((c) => c.id)).toEqual(["today-a", "today-b"])
  })
})
