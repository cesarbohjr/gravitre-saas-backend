import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

/**
 * No-reply/no-audio regression fix (2026-09-06).
 *
 * Root cause, confirmed live: a cold backend worker's first pipecat import
 * took up to ~12.9s (fixed server-side via app-startup warmup — see backend
 * `app.main._import_pipecat_stack`). Before this fix, `getVoiceStatusDetailed`
 * had an 8s client timeout and, on any failure/timeout of a *forced* refresh,
 * unconditionally discarded even a fresh, recently-known-good cached status
 * and returned `null`. `shouldUsePipecatVoice(null)` is `false`, so one slow
 * `/api/voice/status` call silently downgraded an entire voice session to the
 * legacy, less-robust HTTP `<audio>`-element duplex path — which is what then
 * surfaced live as "no reply / audio" plus repeated "Audio playback failed
 * during voice reply" toasts.
 *
 * These tests exercise `getVoiceStatusDetailed`'s fallback behavior directly
 * against a mocked `apiFetch`, so a future refactor cannot silently regress
 * back to discarding a good cached status on a transient failure.
 */

const apiFetchMock = vi.fn()

vi.mock("@/lib/fetcher", () => ({
  apiFetch: (...args: unknown[]) => apiFetchMock(...args),
}))

describe("getVoiceStatusDetailed — status-fetch failure fallback", () => {
  beforeEach(() => {
    vi.resetModules()
    apiFetchMock.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it("reuses a fresh cached status instead of returning null when a forced refresh times out", async () => {
    const { getVoiceStatusDetailed } = await import("@/lib/tier1-voice-client")

    const goodStatus = {
      tts_enabled: true,
      stt_enabled: true,
      pipecat_enabled: true,
      pipecat_available: true,
      pipecat_ws_clients_accepted: true,
    }
    apiFetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => goodStatus,
    })
    const first = await getVoiceStatusDetailed(true)
    expect(first.status?.pipecat_enabled).toBe(true)

    // Second call (a fresh `start()` — always forced) times out / network-fails.
    apiFetchMock.mockRejectedValueOnce(new Error("timeout"))
    const second = await getVoiceStatusDetailed(true)

    expect(second.status).not.toBeNull()
    expect(second.status?.pipecat_enabled).toBe(true)
  })

  it("still returns null on failure when there is no cached status yet (first-ever call)", async () => {
    const { getVoiceStatusDetailed } = await import("@/lib/tier1-voice-client")

    apiFetchMock.mockRejectedValueOnce(new Error("timeout"))
    const result = await getVoiceStatusDetailed(true)

    expect(result.status).toBeNull()
  })

  it("passes a generous (>= 15s) timeout budget to apiFetch for the status check", async () => {
    const { getVoiceStatusDetailed } = await import("@/lib/tier1-voice-client")

    apiFetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ tts_enabled: true, stt_enabled: true }),
    })
    await getVoiceStatusDetailed(true)

    expect(apiFetchMock).toHaveBeenCalledWith(
      "/api/voice/status",
      expect.objectContaining({ timeoutMs: expect.any(Number) }),
    )
    const [, init] = apiFetchMock.mock.calls[0] as [string, { timeoutMs: number }]
    expect(init.timeoutMs).toBeGreaterThanOrEqual(15_000)
  })

  it("still treats an explicit 403 (voice off for org) as a hard null — cache must not mask a real access change", async () => {
    const { getVoiceStatusDetailed } = await import("@/lib/tier1-voice-client")

    const goodStatus = { tts_enabled: true, stt_enabled: true, pipecat_enabled: true }
    apiFetchMock.mockResolvedValueOnce({ ok: true, status: 200, json: async () => goodStatus })
    await getVoiceStatusDetailed(true)

    apiFetchMock.mockResolvedValueOnce({ ok: false, status: 403, json: async () => ({}) })
    const result = await getVoiceStatusDetailed(true)

    expect(result.status).toBeNull()
    expect(result.blocked).toBe(true)
  })
})
