import { describe, expect, it } from "vitest"
import { inspectPcm16Energy } from "@/lib/pipecat-voice-client"

describe("Pipecat PCM audible-energy detection", () => {
  it("classifies empty and digital-silence PCM as inaudible", () => {
    expect(inspectPcm16Energy(new Int16Array())).toEqual({
      peak: 0,
      rms: 0,
      audible: false,
    })
    expect(inspectPcm16Energy(new Int16Array(320))).toMatchObject({
      peak: 0,
      audible: false,
    })
  })

  it("ignores tiny transport noise", () => {
    const pcm = new Int16Array(320)
    pcm.fill(8)
    const result = inspectPcm16Energy(pcm)
    expect(result.peak).toBe(8)
    expect(result.audible).toBe(false)
  })

  it("recognizes low but real speech-like PCM energy", () => {
    const pcm = new Int16Array(320)
    for (let i = 0; i < pcm.length; i++) {
      pcm[i] = i % 2 === 0 ? 240 : -240
    }
    const result = inspectPcm16Energy(pcm)
    expect(result.peak).toBe(240)
    expect(result.rms).toBeGreaterThan(200)
    expect(result.audible).toBe(true)
  })

  it("does not call one isolated spike audible speech", () => {
    const pcm = new Int16Array(320)
    pcm[100] = 500
    const result = inspectPcm16Energy(pcm)
    expect(result.peak).toBe(500)
    expect(result.rms).toBeLessThan(24)
    expect(result.audible).toBe(false)
  })
})
