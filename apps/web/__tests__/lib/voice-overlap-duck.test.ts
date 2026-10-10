import { readFileSync } from "node:fs"
import { join } from "node:path"

import { afterEach, describe, expect, it, vi } from "vitest"

import {
  VOICE_DUCK_GAIN,
  VOICE_DUCK_RAMP_S,
  VOICE_UNDUCK_RAMP_S,
  createOverlapDuckState,
  rampDuckGain,
} from "@/lib/voice-overlap-duck"
import { PCM_FLUSH_FADE_S, createBufferSourcePcmPlayer, createWorkletPcmPlayer } from "@/lib/voice-pcm-player"

type Call = [string, ...number[]]

/** An AudioParam that records its automation calls. */
function fakeParam(calls: Call[]) {
  return {
    value: 1,
    cancelScheduledValues: (t: number) => calls.push(["cancel", t]),
    setValueAtTime: (v: number, t: number) => calls.push(["set", v, t]),
    linearRampToValueAtTime: (v: number, t: number) => calls.push(["ramp", v, t]),
  }
}

function fakeCtx() {
  const gains: Array<{ calls: Call[]; connectedTo: unknown[] }> = []
  const createGain = () => {
    const calls: Call[] = []
    const connectedTo: unknown[] = []
    gains.push({ calls, connectedTo })
    return { gain: fakeParam(calls), connect: (n: unknown) => connectedTo.push(n), disconnect() {} }
  }
  const ctx = {
    currentTime: 0,
    sampleRate: 48000,
    destination: { name: "destination" },
    createGain,
    createBuffer: (_c: number, length: number) => ({ length, copyToChannel() {} }),
    createBufferSource: () => ({ buffer: null, onended: null, connect() {}, start() {}, stop() {} }),
  }
  return { ctx: ctx as unknown as AudioContext & { currentTime: number }, gains }
}

function stubWorkletNode() {
  class FakeNode {
    port = { onmessage: null, postMessage() {} }
    connected: unknown[] = []
    connect(n: unknown) {
      this.connected.push(n)
    }
    disconnect() {}
  }
  vi.stubGlobal("AudioWorkletNode", FakeNode)
}

describe("rampDuckGain", () => {
  it("ducks to ~0.15 over ~60 ms and restores over ~120 ms, from the current value", () => {
    expect(VOICE_DUCK_GAIN).toBeCloseTo(0.15)
    expect(VOICE_DUCK_RAMP_S).toBeCloseTo(0.06)
    expect(VOICE_UNDUCK_RAMP_S).toBeCloseTo(0.12)
    const calls: Call[] = []
    const param = fakeParam(calls)
    rampDuckGain(param, 2, true)
    expect(calls).toEqual([
      ["cancel", 2],
      ["set", 1, 2],
      ["ramp", 0.15, 2 + 0.06],
    ])
    calls.length = 0
    param.value = 0.4 // mid-ramp
    rampDuckGain(param, 2.03, false)
    expect(calls).toEqual([
      ["cancel", 2.03],
      ["set", 0.4, 2.03],
      ["ramp", 1, 2.03 + 0.12],
    ])
  })
})

describe("overlap duck state", () => {
  it("ducks once, and unducks only when ducked", () => {
    const s = createOverlapDuckState()
    expect(s.unduck(1)).toBe(false)
    expect(s.duck(1)).toBe(true)
    expect(s.duck(1)).toBe(false)
    expect(s.isDucked()).toBe(true)
    expect(s.unduck(1)).toBe(true)
    expect(s.isDucked()).toBe(false)
  })

  it("audio of a newer reply ends the duck; the ducked reply's own audio does not", () => {
    const s = createOverlapDuckState()
    s.audio(3)
    s.duck(3)
    expect(s.audio(3)).toBe(false)
    expect(s.isDucked()).toBe(true)
    expect(s.audio(4)).toBe(true)
    expect(s.isDucked()).toBe(false)
  })

  it("ignores a duck for a reply that is already over", () => {
    const s = createOverlapDuckState()
    s.audio(5)
    expect(s.duck(4)).toBe(false)
    expect(s.isDucked()).toBe(false)
  })

  it("reset (speech.interrupted, flush, new session) reports whether it was ducked", () => {
    const s = createOverlapDuckState()
    expect(s.reset()).toBe(false)
    s.duck(1)
    expect(s.reset()).toBe(true)
    expect(s.isDucked()).toBe(false)
  })
})

describe("PCM players route through a duck gain stage", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("worklet player: duck, restore, and a flush resets to full gain after its fade", () => {
    stubWorkletNode()
    const { ctx, gains } = fakeCtx()
    const player = createWorkletPcmPlayer(ctx)
    expect(gains).toHaveLength(1)
    const duck = gains[0]
    expect(duck.connectedTo).toEqual([ctx.destination])

    ctx.currentTime = 1
    player.setDuck(true)
    expect(duck.calls.at(-1)).toEqual(["ramp", VOICE_DUCK_GAIN, 1 + VOICE_DUCK_RAMP_S])
    const before = duck.calls.length
    player.setDuck(true) // no-op
    expect(duck.calls).toHaveLength(before)

    ctx.currentTime = 1.5
    player.setDuck(false)
    expect(duck.calls.at(-1)).toEqual(["ramp", 1, 1.5 + VOICE_UNDUCK_RAMP_S])

    player.setDuck(true)
    ctx.currentTime = 2
    player.flush()
    expect(duck.calls.at(-1)).toEqual(["set", 1, 2 + PCM_FLUSH_FADE_S])
    // After the flush the player is not ducked: the next duck ramps again.
    player.setDuck(true)
    expect(duck.calls.at(-1)).toEqual(["ramp", VOICE_DUCK_GAIN, 2 + VOICE_DUCK_RAMP_S])
  })

  it("buffer-source player: the per-flush gain feeds the duck stage", () => {
    const { ctx, gains } = fakeCtx()
    const player = createBufferSourcePcmPlayer(ctx)
    // [0] duck stage -> destination, [1] the flushable output -> duck stage.
    expect(gains[0].connectedTo).toEqual([ctx.destination])
    expect(gains[1].connectedTo).toHaveLength(1)
    expect(gains[1].connectedTo[0]).not.toBe(ctx.destination)
    player.setDuck(true)
    expect(gains[0].calls.at(-1)).toEqual(["ramp", VOICE_DUCK_GAIN, VOICE_DUCK_RAMP_S])
    vi.useFakeTimers()
    try {
      player.flush()
    } finally {
      vi.useRealTimers()
    }
    expect(gains[0].calls.at(-1)).toEqual(["set", 1, PCM_FLUSH_FADE_S])
    // The new output gain after the flush also goes through the duck stage.
    expect(gains[2].connectedTo).toEqual(gains[1].connectedTo)
  })
})

describe("duplex hook duck handling", () => {
  const src = readFileSync(join(__dirname, "../../hooks/use-voice-duplex-session.ts"), "utf8")
  const at = src.indexOf('if (kind === "speech.duck" || kind === "speech.unduck")')
  const block = src.slice(at, src.indexOf("return\n        }", at))

  it("handles speech.duck / speech.unduck before speech.interrupted", () => {
    expect(at).toBeGreaterThan(0)
    expect(at).toBeLessThan(src.indexOf('if (kind === "speech.interrupted"'))
    expect(block).toContain("setDuck(true)")
    expect(block).toContain("setDuck(false)")
    expect(block).toContain("isInterruptedReplyAudio")
  })

  it("resets the duck on every interruption, flush, new reply and new session", () => {
    const stop = src.slice(src.indexOf("const stopPcmPlayback"), src.indexOf("const stopPlayback = "))
    expect(stop).toContain("overlapDuckRef.current.reset()")
    const speechStop = src.slice(
      src.indexOf('if (kind === "speech.interrupted" && speechInterruptionKind(msg) === "speech_stop")'),
      src.indexOf('if (kind === "speech.interrupted") {'),
    )
    expect(speechStop).toContain("endOverlapDuck()")
    const interrupt = src.slice(
      src.indexOf('if (kind === "speech.interrupted") {'),
      src.indexOf("if (msg.reconcile_played_audio !== true) return"),
    )
    expect(interrupt).toContain("endOverlapDuck()")
    const audio = src.slice(src.indexOf('if (kind === "audio" && typeof msg.pcm16_b64 === "string")'))
    expect(audio.slice(0, 800)).toContain("overlapDuckRef.current.audio(msg.reply_id)")
    expect(src).toMatch(/interruptedReplyIdRef\.current = null\n\s*overlapDuckRef\.current = createOverlapDuckState\(\)/)
  })
})
