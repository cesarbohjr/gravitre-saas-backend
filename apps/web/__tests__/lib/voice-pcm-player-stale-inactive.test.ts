import { afterEach, describe, expect, it, vi } from "vitest"

import { createWorkletPcmPlayer } from "@/lib/voice-pcm-player"

type Port = { onmessage: ((e: MessageEvent) => void) | null; postMessage: (m: unknown) => void }

function fakeWorkletEnv() {
  const posted: unknown[] = []
  const port: Port = { onmessage: null, postMessage: (m) => posted.push(m) }
  class FakeNode {
    port = port
    connect() {}
    disconnect() {}
  }
  vi.stubGlobal("AudioWorkletNode", FakeNode)
  const createGain = () => ({ gain: { value: 1, cancelScheduledValues() {}, setValueAtTime() {}, linearRampToValueAtTime() {} }, connect() {}, disconnect() {} })
  const ctx = { currentTime: 0, sampleRate: 48000, destination: {}, createGain } as unknown as AudioContext
  const emit = (data: unknown) => port.onmessage?.({ data } as MessageEvent)
  return { ctx, posted, emit }
}

describe("worklet PCM player after a barge-in flush", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("ignores an inactive report that audio posted after the flush has overtaken", () => {
    const { ctx, emit } = fakeWorkletEnv()
    const changes: boolean[] = []
    const player = createWorkletPcmPlayer(ctx, { onActiveChange: (a) => changes.push(a) })

    player.enqueue(new Int16Array(960), 24000) // seq 1
    emit({ type: "active", active: true, seq: 1 })
    player.flush()
    player.enqueue(new Int16Array(960), 24000) // seq 2, the next reply
    // The flush fade finished before the worklet saw seq 2.
    emit({ type: "active", active: false, seq: 1 })

    expect(player.isActive()).toBe(true)
    expect(changes).toEqual([true])
  })

  it("still reports inactive once the worklet has drained everything posted", () => {
    const { ctx, emit } = fakeWorkletEnv()
    const changes: boolean[] = []
    const player = createWorkletPcmPlayer(ctx, { onActiveChange: (a) => changes.push(a) })

    player.enqueue(new Int16Array(960), 24000)
    emit({ type: "active", active: true, seq: 1 })
    emit({ type: "active", active: false, seq: 1 })

    expect(player.isActive()).toBe(false)
    expect(changes).toEqual([true, false])
  })
})
