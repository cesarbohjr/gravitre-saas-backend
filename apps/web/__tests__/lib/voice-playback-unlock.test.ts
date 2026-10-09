import { describe, expect, it, vi } from "vitest"
import {
  ensureAudioOutputRunning,
  isResumableAudioState,
} from "@/lib/voice-playback-unlock"

function fakeContext(initial: string, resumeTo: string | null) {
  const ctx = {
    state: initial,
    resume: vi.fn(async () => {
      if (resumeTo) ctx.state = resumeTo
    }),
  }
  return ctx as unknown as AudioContext & { resume: ReturnType<typeof vi.fn> }
}

describe("isResumableAudioState", () => {
  it("treats Safari's interrupted state as resumable", () => {
    expect(isResumableAudioState("interrupted")).toBe(true)
    expect(isResumableAudioState("suspended")).toBe(true)
    expect(isResumableAudioState("running")).toBe(false)
    expect(isResumableAudioState("closed")).toBe(false)
  })
})

describe("ensureAudioOutputRunning", () => {
  it("resumes an interrupted iOS context", async () => {
    const ctx = fakeContext("interrupted", "running")
    await expect(ensureAudioOutputRunning(ctx)).resolves.toBe(true)
    expect(ctx.resume).toHaveBeenCalledTimes(1)
  })

  it("does not hang when resume never settles", async () => {
    const ctx = {
      state: "interrupted",
      resume: vi.fn(() => new Promise<void>(() => {})),
    } as unknown as AudioContext
    await expect(ensureAudioOutputRunning(ctx, 20)).resolves.toBe(false)
  })

  it("leaves a running context alone", async () => {
    const ctx = fakeContext("running", null)
    await expect(ensureAudioOutputRunning(ctx)).resolves.toBe(true)
    expect(ctx.resume).not.toHaveBeenCalled()
  })
})
