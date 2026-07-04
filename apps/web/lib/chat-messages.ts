import type { UIMessage } from "ai"
import type { ConversationMessage } from "@/types/api"
import { splitConversationMessages } from "@/lib/ai-inline-turn-persistence"

export function conversationMessageToUI(message: ConversationMessage): UIMessage {
  return {
    id: message.id,
    role: message.role === "assistant" ? "assistant" : "user",
    parts: [{ type: "text", text: message.content }],
  }
}

export function conversationMessagesToUI(messages: ConversationMessage[]): UIMessage[] {
  const { chatMessages } = splitConversationMessages(messages)
  return chatMessages.map(conversationMessageToUI)
}
