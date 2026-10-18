import { afterEach, describe, expect, it, vi } from "vitest"
import { buildDuplexControls, type DuplexSessionLike } from "@/lib/voice-duplex-controls"

const session = {
  isActive: false,
  presence: "idle",
  toggle: vi.fn(),
  bargeIn: vi.fn(),
  resumeBlockedPlayback: vi.fn(),
} as unknown as DuplexSessionLike

describe("shared chat/voice duplex capability contract", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("does not show a live voice affordance when mediaDevices exists without getUserMedia", () => {
    vi.stubGlobal("navigator", { mediaDevices: {} })
    expect(buildDuplexControls(session).supported).toBe(false)
  })

  it("shows live voice only with actual microphone capture support", () => {
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn() } })
    expect(buildDuplexControls(session).supported).toBe(true)
  })

  it("preserves playback-blocked state from either audio path", () => {
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia: vi.fn() } })
    const controls = buildDuplexControls(session, { alsoPlaybackBlocked: true })
    expect(controls.playbackBlocked).toBe(true)
  })
})
