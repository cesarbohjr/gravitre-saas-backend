import { beforeEach, describe, expect, it, vi } from "vitest"

const apiFetch = vi.fn()

vi.mock("@/lib/fetcher", () => ({
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}))

describe("stopChatTurn", () => {
  beforeEach(() => {
    apiFetch.mockReset()
    apiFetch.mockResolvedValue({ ok: true })
  })

  it("posts conversation_id then aborts the local stream", async () => {
    const { stopChatTurn } = await import("@/lib/chat-stop")
    const stopStream = vi.fn()
    stopChatTurn({ conversationId: "conv-123", stopStream })
    expect(stopStream).toHaveBeenCalledTimes(1)
    await vi.waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/chat/stop",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ conversation_id: "conv-123" }),
        }),
      )
    })
  })

  it("skips the network call when conversation_id is missing", async () => {
    const { requestChatTurnStop } = await import("@/lib/chat-stop")
    await requestChatTurnStop("  ")
    expect(apiFetch).not.toHaveBeenCalled()
  })
})
