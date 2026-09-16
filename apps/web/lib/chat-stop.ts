import { apiFetch } from "@/lib/fetcher"

/** Signal the backend to abort the in-flight governed turn, then abort the SSE reader. */
export async function requestChatTurnStop(conversationId: string | null | undefined): Promise<void> {
  const id = conversationId?.trim()
  if (!id) return
  try {
    await apiFetch("/api/chat/stop", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ conversation_id: id }),
      timeoutMs: 8_000,
    })
  } catch {
    // Client abort still disconnects the stream; Redis flag is best-effort.
  }
}

export function stopChatTurn(options: {
  conversationId: string | null | undefined
  stopStream: () => void
}): void {
  void requestChatTurnStop(options.conversationId)
  options.stopStream()
}
