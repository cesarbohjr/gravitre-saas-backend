import { describe, expect, it } from "vitest"
import { encodePipecatPlaybackStarted, inspectPcm16Energy } from "@/lib/pipecat-voice-client"

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
    pcm[100] = 300
    const result = inspectPcm16Energy(pcm)
    expect(result.peak).toBe(300)
    expect(result.rms).toBeLessThan(24)
    expect(result.audible).toBe(false)
  })
})

describe("encodePipecatPlaybackStarted", () => {
  it("reports the browser-side receive-to-playback delta in whole milliseconds", () => {
    expect(JSON.parse(encodePipecatPlaybackStarted(119.6) as string)).toEqual({
      type: "playback.started",
      receive_to_playback_ms: 120,
    })
  })

  it("sends nothing for a negative or non-finite delta", () => {
    expect(encodePipecatPlaybackStarted(-1)).toBeNull()
    expect(encodePipecatPlaybackStarted(Number.NaN)).toBeNull()
  })
})
