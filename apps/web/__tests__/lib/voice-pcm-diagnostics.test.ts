import { afterEach, describe, expect, it, vi } from "vitest"
import { createPcmDiagnostics } from "@/lib/voice-pcm-diagnostics"
import { createWorkletPcmPlayer } from "@/lib/voice-pcm-player"

function playerFixture() {
  const port = { onmessage: null as ((e: MessageEvent) => void) | null, postMessage() {} }
  class FakeNode {
    port = port
    connect() {}
    disconnect() {}
  }
  vi.stubGlobal("AudioWorkletNode", FakeNode)
  const gain = () => ({ gain: { value: 1, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime() {} }, connect() {}, disconnect() {} })
  const ctx = { currentTime: 0, sampleRate: 48000, destination: {}, createGain: gain } as unknown as AudioContext
  const player = createWorkletPcmPlayer(ctx)
  return { ctx, player, emit: (data: unknown) => port.onmessage?.({ data } as MessageEvent) }
}

describe("content-free PCM continuity observations", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("counts duck duration and transitions without resetting lifetime evidence on flush", () => {
    let now = 0
    const metrics = createPcmDiagnostics("worklet", () => now)
    metrics.noteQueue(2, 120)
    metrics.setDuck(true)
    metrics.setDuck(true)
    now = 0.2
    expect(metrics.snapshot().ducked_ms).toBe(200)
    metrics.flush()
    expect(metrics.snapshot()).toEqual({ player_kind: "worklet", observed_underruns: 2, buffered_ms: 0, ducked: false, duck_transitions: 2, ducked_ms: 200, flush_count: 1 })
  })

  it("ignores invalid measurements and never decreases lifetime underruns", () => {
    const metrics = createPcmDiagnostics("buffer-source", () => 0)
    metrics.noteQueue(3, 100)
    metrics.noteQueue(1, -5)
    metrics.noteQueue(Infinity, NaN)
    expect(metrics.snapshot().observed_underruns).toBe(3)
    expect(metrics.snapshot().buffered_ms).toBe(100)
  })

  it("consumes actual worklet reports and rejects reports from an old flush epoch", () => {
    const { player, emit } = playerFixture()
    emit({ type: "progress", epoch: 0, played: 48, frame: 48, underruns: 2, buffered_frames: 4800 })
    expect(player.diagnostics?.().buffered_ms).toBe(100)
    player.flush()
    emit({ type: "progress", epoch: 0, played: 96, underruns: 99, buffered_frames: 9600 })
    expect(player.diagnostics?.().observed_underruns).toBe(2)
    expect(player.diagnostics?.().buffered_ms).toBe(0)
  })

  it("ignores a delayed pre-flush start without changing the new reply's origin", () => {
    const observed: number[] = []
    const port = { onmessage: null as ((e: MessageEvent) => void) | null, postMessage() {} }
    class FakeNode {
      port = port
      connect() {}
      disconnect() {}
    }
    vi.stubGlobal("AudioWorkletNode", FakeNode)
    const gain = () => ({ gain: { value: 1, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime() {} }, connect() {}, disconnect() {} })
    const ctx = { currentTime: 1, sampleRate: 48000, destination: {}, createGain: gain } as unknown as AudioContext
    const player = createWorkletPcmPlayer(ctx, { onStarted: (at) => observed.push(at) })
    player.enqueue(new Int16Array(960), 24000)
    player.flush()
    port.onmessage?.({ data: { type: "started", frame: 48000, epoch: 0 } } as MessageEvent)
    expect(observed).toEqual([])
    expect(player.originTime()).toBeNull()
    port.onmessage?.({ data: { type: "started", frame: 52800, epoch: 1 } } as MessageEvent)
    expect(observed).toEqual([1.1])
    expect(player.originTime()).toBe(1.1)
  })

  it("ignores stale inactive reports and reports duck/flush from the real player", () => {
    const { player, ctx, emit } = playerFixture()
    player.enqueue(new Int16Array(960), 24000)
    emit({ type: "active", active: false, seq: 0, epoch: 0, underruns: 99 })
    expect(player.diagnostics?.().observed_underruns).toBe(0)
    player.setDuck(true)
    Object.assign(ctx, { currentTime: 0.25 })
    player.flush()
    expect(player.diagnostics?.().ducked_ms).toBe(250)
    expect(player.diagnostics?.().flush_count).toBe(1)
    expect(player.diagnostics?.().ducked).toBe(false)
  })
})
