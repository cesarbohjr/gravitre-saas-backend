import type { Conversation, ConversationMessage } from "@/types/api"

type ConversationRow = {
  id: string
  title: string | null
  preview: string | null
  message_count: number | null
  created_at: string
  updated_at: string
}

type ConversationMessageRow = {
  id: string
  conversation_id: string
  role: string
  content: string
  tool_calls: unknown[] | null
  created_at: string
}

export function mapConversationRow(row: ConversationRow): Conversation {
  return {
    id: String(row.id),
    title: row.title?.trim() || "New conversation",
    preview: row.preview ?? undefined,
    created_at: row.created_at,
    updated_at: row.updated_at,
    message_count: Number(row.message_count ?? 0),
  }
}

export function mapConversationMessageRow(row: ConversationMessageRow): ConversationMessage {
  return {
    id: String(row.id),
    conversation_id: String(row.conversation_id),
    role: row.role === "assistant" ? "assistant" : "user",
    content: row.content ?? "",
    tool_calls: row.tool_calls ?? undefined,
    created_at: row.created_at,
  }
}
