import { describe, expect, it } from "vitest"
import {
  PCM_JITTER_INITIAL_LEAD_S,
  PCM_JITTER_MAX_LEAD_S,
  createPcmJitterState,
  schedulePcmStart,
} from "@/lib/voice-pcm-jitter"

const CHUNK_S = 0.04

/** Feed chunks arriving at the given wall-clock times (ms); return gaps heard. */
function simulate(arrivalsMs: number[]) {
  const state = createPcmJitterState()
  let next = 0
  let gaps = 0
  for (const at of arrivalsMs) {
    const now = at / 1000
    const start = schedulePcmStart(state, now, next, at)
    if (next > 0 && start > next + 1e-6) gaps += 1
    next = start + CHUNK_S
  }
  return { gaps, state }
}

describe("voice PCM jitter buffer", () => {
  it("starts a reply one lead ahead, then plays chunks back to back", () => {
    const state = createPcmJitterState()
    const first = schedulePcmStart(state, 10, 0, 10_000)
    expect(first).toBeCloseTo(10 + PCM_JITTER_INITIAL_LEAD_S)
    const second = schedulePcmStart(state, 10.04, first + CHUNK_S, 10_040)
    expect(second).toBeCloseTo(first + CHUNK_S)
  })

  it("absorbs real-time pacing with up to 100 ms of network jitter without a gap", () => {
    // Server sends every 40 ms; each arrival is late by a different amount.
    const jitter = [0, 90, 10, 100, 0, 60, 95, 20, 0, 80]
    const arrivals = jitter.map((j, i) => 1000 + i * 40 + j)
    expect(simulate(arrivals).gaps).toBe(0)
  })

  it("the old 10 ms lead breaks up on the same jitter", () => {
    const jitter = [0, 90, 10, 100, 0, 60, 95, 20, 0, 80]
    let next = 0
    let gaps = 0
    jitter.forEach((j, i) => {
      const now = (1000 + i * 40 + j) / 1000
      const start = Math.max(now + 0.01, next)
      if (next > 0 && start > next + 1e-6) gaps += 1
      next = start + CHUNK_S
    })
    expect(gaps).toBeGreaterThan(0)
  })

  it("grows the lead after a mid-reply underrun, capped", () => {
    const state = createPcmJitterState()
    let next = schedulePcmStart(state, 1, 0, 1000) + CHUNK_S
    // A 500 ms stall inside the reply (chunks still arriving <400 ms apart).
    for (let i = 0; i < 10; i++) {
      const at = 1000 + 300 * (i + 1)
      next = schedulePcmStart(state, at / 1000, next, at) + CHUNK_S
    }
    expect(state.underruns).toBeGreaterThan(0)
    expect(state.leadS).toBeGreaterThan(PCM_JITTER_INITIAL_LEAD_S)
    expect(state.leadS).toBeLessThanOrEqual(PCM_JITTER_MAX_LEAD_S)
  })

  it("does not count the pause between two replies as an underrun", () => {
    const state = createPcmJitterState()
    const end = schedulePcmStart(state, 1, 0, 1000) + CHUNK_S
    schedulePcmStart(state, 5, end, 5000)
    expect(state.underruns).toBe(0)
    expect(state.leadS).toBe(PCM_JITTER_INITIAL_LEAD_S)
  })
})
