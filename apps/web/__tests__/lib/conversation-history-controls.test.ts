import { describe, expect, it } from "vitest"
import {
  emptyHistoryMessage,
  matchesHistoryDateFilter,
  optimisticRemoveConversations,
  parseHistorySort,
  sortConversations,
  type HistoryDateFilter,
} from "@/lib/conversation-history-controls"
import type { Conversation } from "@/types/api"

function conversation(partial: Partial<Conversation> & { id: string }): Conversation {
  return {
    org_id: "org",
    user_id: "user",
    title: partial.title ?? partial.id,
    preview: null,
    message_count: 0,
    created_at: "2026-10-01T00:00:00.000Z",
    updated_at: partial.updated_at ?? "2026-10-01T12:00:00.000Z",
    ...partial,
  } as Conversation
}

describe("conversation history controls", () => {
  const now = new Date("2026-10-01T15:00:00.000Z")

  it("filters today/week/archived without mixing archived into live lists", () => {
    const live = conversation({ id: "a", updated_at: "2026-10-01T14:00:00.000Z" })
    const old = conversation({ id: "b", updated_at: "2026-09-01T14:00:00.000Z" })
    const archived = conversation({
      id: "c",
      updated_at: "2026-10-01T14:00:00.000Z",
      archived_at: "2026-10-01T14:30:00.000Z",
    })

    expect(matchesHistoryDateFilter(live, "today", now)).toBe(true)
    expect(matchesHistoryDateFilter(old, "today", now)).toBe(false)
    expect(matchesHistoryDateFilter(old, "all", now)).toBe(true)
    expect(matchesHistoryDateFilter(archived, "all", now)).toBe(false)
    expect(matchesHistoryDateFilter(archived, "archived", now)).toBe(true)
  })

  it("sorts newest and oldest while keeping pinned first", () => {
    const rows = [
      conversation({ id: "new", updated_at: "2026-10-01T14:00:00.000Z" }),
      conversation({ id: "old", updated_at: "2026-09-01T14:00:00.000Z" }),
      conversation({ id: "pin", updated_at: "2026-08-01T14:00:00.000Z", pinned_at: "2026-10-01T00:00:00.000Z" }),
    ]
    expect(sortConversations(rows, "newest").map((row) => row.id)).toEqual(["pin", "new", "old"])
    expect(sortConversations(rows, "oldest").map((row) => row.id)).toEqual(["pin", "old", "new"])
  })

  it("optimistically removes deleted ids from the list cache", () => {
    const current = {
      conversations: [conversation({ id: "keep" }), conversation({ id: "gone" })],
    }
    expect(optimisticRemoveConversations(current, ["gone"])?.conversations.map((row) => row.id)).toEqual(["keep"])
  })

  it("parses sort and empty copy", () => {
    expect(parseHistorySort("oldest")).toBe("oldest")
    expect(parseHistorySort("nope")).toBe("newest")
    expect(emptyHistoryMessage("archived" as HistoryDateFilter, "")).toContain("archived")
  })
})
