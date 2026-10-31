import { describe, expect, it, vi } from "vitest"
import { LocalCancellationShadowProbe } from "../voice-local-cancel-shadow-probe"

describe("local cancellation shadow PCM adapter", () => {
  it("buffers 16kHz PCM into exact nonoverlapping frames without runtime writes", async () => {
    let now = 0
    const process = vi.fn(async (_frame: Int16Array) => true)
    const sink = vi.fn()
    const probe = new LocalCancellationShadowProbe(
      { sampleRate: 16000, frameLength: 4, process }, sink, () => now,
    )
    await probe.consume(new Int16Array([1, 2]), true)
    expect(process).toHaveBeenCalledTimes(0)
    now = 200
    await probe.consume(new Int16Array([3, 4, 5, 6, 7, 8]), true)
    expect(process).toHaveBeenCalledTimes(2)
    expect(Array.from(process.mock.calls[0][0])).toEqual([1, 2, 3, 4])
    expect(Array.from(process.mock.calls[1][0])).toEqual([5, 6, 7, 8])
    expect(sink).toHaveBeenCalledTimes(2)
    expect(sink.mock.calls[0][1]).toEqual({ status: "observed", latencyMs: 200 })
    probe.dispose()
    await expect(probe.consume(new Int16Array([1, 2, 3, 4]), true)).rejects.toThrow("disposed")
  })
  it("discards buffered audio when active work ends", async () => {
    const process = vi.fn(() => false)
    const probe = new LocalCancellationShadowProbe(
      { sampleRate: 16000, frameLength: 4, process }, () => {},
    )
    await probe.consume(new Int16Array([1, 2]), true)
    await probe.consume(new Int16Array([3, 4]), false)
    await probe.consume(new Int16Array([5, 6]), true)
    expect(process).not.toHaveBeenCalled()
  })
  it("rejects unsupported audio rates and malformed frames", () => {
    expect(() => new LocalCancellationShadowProbe(
      { sampleRate: 8000 as 16000, frameLength: 4, process: () => false }, () => {},
    )).toThrow("16kHz")
    expect(() => new LocalCancellationShadowProbe(
      { sampleRate: 16000, frameLength: 0, process: () => false }, () => {},
    )).toThrow("frame length")
  })
})
