import { afterAll, beforeAll, describe, expect, it } from "vitest"
import {
  PcmPlayoutQueue,
  StreamingResampler,
  floatArrayToInt16,
  floatToInt16,
  int16ArrayToFloat,
} from "@/public/voice-worklets/voice-dsp.js"
import { base64ToPcm16, createPcm16StreamDecoder, pcm16ToBase64 } from "@/lib/pipecat-voice-client"

function tone(freq: number, rate: number, n: number, amp = 0.5, phase0 = 0): Float32Array {
  const out = new Float32Array(n)
  for (let i = 0; i < n; i++) out[i] = amp * Math.sin(2 * Math.PI * freq * (i / rate) + phase0)
  return out
}

function rms(x: Float32Array, from = 0, to = x.length): number {
  let s = 0
  for (let i = from; i < to; i++) s += x[i] * x[i]
  return Math.sqrt(s / Math.max(1, to - from))
}

function concat(parts: Float32Array[]): Float32Array {
  const out = new Float32Array(parts.reduce((n, p) => n + p.length, 0))
  let o = 0
  for (const p of parts) {
    out.set(p, o)
    o += p.length
  }
  return out
}

function maxJump(x: Float32Array, from = 1, to = x.length): number {
  let m = 0
  for (let i = Math.max(1, from); i < to; i++) m = Math.max(m, Math.abs(x[i] - x[i - 1]))
  return m
}

function resampleInBlocks(r: StreamingResampler, input: Float32Array, block: number): Float32Array {
  const parts: Float32Array[] = []
  for (let i = 0; i < input.length; i += block) parts.push(r.process(input.subarray(i, i + block)))
  parts.push(r.flush())
  return concat(parts)
}

describe("PCM16 conversion", () => {
  it("clamps instead of wrapping on overflow", () => {
    expect(floatToInt16(1)).toBe(32767)
    expect(floatToInt16(1.7)).toBe(32767)
    expect(floatToInt16(-1)).toBe(-32768)
    expect(floatToInt16(-3)).toBe(-32768)
    expect(floatToInt16(Number.NaN)).toBe(0)
    // Gain pushes past full scale: still clamped, never sign-flipped.
    const out = floatArrayToInt16(new Float32Array([0.9, -0.9]), 1.5)
    expect(Array.from(out)).toEqual([32767, -32768])
  })

  it("round-trips int16 through float", () => {
    const pcm = new Int16Array([0, 1, -1, 32767, -32768, 12345])
    const back = floatArrayToInt16(int16ArrayToFloat(pcm))
    // Positive full scale maps 32767/32768 -> *32767, within one LSB.
    for (let i = 0; i < pcm.length; i++) expect(Math.abs(back[i] - pcm[i])).toBeLessThanOrEqual(1)
  })

  it("decodes little-endian bytes", () => {
    const b64 = btoa(String.fromCharCode(0x01, 0x80, 0xff, 0x7f))
    expect(Array.from(base64ToPcm16(b64))).toEqual([-32767, 32767])
  })
})

describe("PCM16 stream decoder", () => {
  const source = floatArrayToInt16(tone(440, 24000, 2400))
  const bytes = new Uint8Array(source.buffer)
  // Odd split points: every message boundary falls inside a sample.
  const splits = [1, 961, 1921, 3843, 4801]
  const messages: string[] = []
  let prev = 0
  for (const at of [...splits, bytes.length]) {
    messages.push(btoa(String.fromCharCode(...bytes.subarray(prev, at))))
    prev = at
  }

  it("reassembles samples split across messages", () => {
    const decoder = createPcm16StreamDecoder()
    const parts = messages.map((m) => decoder.decode(m))
    const out = new Int16Array(parts.reduce((n, p) => n + p.length, 0))
    let o = 0
    for (const p of parts) {
      out.set(p, o)
      o += p.length
    }
    expect(Array.from(out)).toEqual(Array.from(source))
  })

  it("documents the old per-message decode corrupting everything after an odd boundary", () => {
    const parts = messages.map((m) => base64ToPcm16(m))
    const total = parts.reduce((n, p) => n + p.length, 0)
    expect(total).toBeLessThan(source.length)
    // The second message starts on the high byte of a sample: garbage.
    const second = parts[1]
    let wrong = 0
    for (let i = 0; i < second.length; i++) if (Math.abs(second[i] - source[i + 1]) > 256) wrong += 1
    expect(wrong).toBeGreaterThan(second.length * 0.5)
  })

  it("reset drops a pending half sample", () => {
    const decoder = createPcm16StreamDecoder()
    decoder.decode(btoa(String.fromCharCode(0x34)))
    decoder.reset()
    expect(Array.from(decoder.decode(pcm16ToBase64(new Int16Array([7]))))).toEqual([7])
  })
})

describe("StreamingResampler", () => {
  for (const inRate of [48000, 44100]) {
    it(`${inRate} -> 16000 keeps speech and rejects what would alias`, () => {
      const n = inRate // 1 s
      const pass = resampleInBlocks(new StreamingResampler(inRate, 16000), tone(1000, inRate, n), 4096)
      expect(pass.length).toBeGreaterThanOrEqual(15999)
      expect(pass.length).toBeLessThanOrEqual(16001)
      // 0.5 amplitude sine -> rms 0.3536
      expect(rms(pass, 800, 15000)).toBeCloseTo(0.3536, 2)

      // 13 kHz would fold to 3 kHz with plain decimation (the old capture path).
      const stop = resampleInBlocks(new StreamingResampler(inRate, 16000), tone(13000, inRate, n), 4096)
      const attenuationDb = 20 * Math.log10(rms(stop, 800, 15000) / 0.3536)
      expect(attenuationDb).toBeLessThan(-50)

      // Reference: what the old decimation did with the same 13 kHz tone.
      const ratio = inRate / 16000
      const naive = new Float32Array(Math.floor(n / ratio))
      const src = tone(13000, inRate, n)
      for (let i = 0; i < naive.length; i++) naive[i] = src[Math.floor(i * ratio)]
      expect(20 * Math.log10(rms(naive) / 0.3536)).toBeGreaterThan(-3)
    })
  }

  it("is block-size invariant (no state lost at block edges)", () => {
    const input = tone(700, 44100, 44100)
    const whole = resampleInBlocks(new StreamingResampler(44100, 16000), input, input.length)
    const blocks = resampleInBlocks(new StreamingResampler(44100, 16000), input, 4096)
    const odd = resampleInBlocks(new StreamingResampler(44100, 16000), input, 127)
    expect(blocks.length).toBe(whole.length)
    expect(odd.length).toBe(whole.length)
    for (let i = 0; i < whole.length; i++) {
      expect(Math.abs(blocks[i] - whole[i])).toBeLessThan(1e-5)
      expect(Math.abs(odd[i] - whole[i])).toBeLessThan(1e-5)
    }
  })

  it("flush emits exactly the held-back tail, whatever the buffer state", () => {
    const input = tone(440, 24000, 24000)
    for (const chunk of [960, 961, 1000, 37, 4096]) {
      for (const outRate of [48000, 44100]) {
        const whole = new StreamingResampler(24000, outRate)
        const ref = concat([whole.process(input), whole.flush()])
        const r = new StreamingResampler(24000, outRate)
        const parts: Float32Array[] = []
        for (let i = 0; i < input.length; i += chunk) parts.push(r.process(input.subarray(i, i + chunk)))
        parts.push(r.flush())
        const got = concat(parts)
        expect(got.length).toBe(ref.length)
        expect(got.length).toBe(Math.ceil((input.length * outRate) / 24000))
        let err = 0
        for (let i = 0; i < ref.length; i++) err = Math.max(err, Math.abs(got[i] - ref[i]))
        expect(err).toBeLessThan(1e-5)
        // A flush mid-stream must not inject silence (it used to, after the
        // buffer had compacted).
        const r2 = new StreamingResampler(24000, outRate)
        const a = r2.process(input.subarray(0, chunk * 3))
        const tail = r2.flush()
        expect(a.length + tail.length).toBe(Math.ceil((chunk * 3 * outRate) / 24000))
      }
    }
  })

  for (const outRate of [48000, 44100]) {
    it(`24000 -> ${outRate} in 40 ms chunks has no boundary discontinuities`, () => {
      const input = tone(440, 24000, 24000)
      const out = resampleInBlocks(new StreamingResampler(24000, outRate), input, 960)
      const expected = 2 * Math.PI * 440 * 0.5 / outRate
      // Skip the filter warm-up at the very start.
      expect(maxJump(out, 64, out.length - 64)).toBeLessThan(expected * 1.05)
      expect(rms(out, 1000, out.length - 1000)).toBeCloseTo(0.3536, 2)
    })
  }
})

describe("PcmPlayoutQueue", () => {
  const RATE = 48000
  const Q = 128

  function run(queue: PcmPlayoutQueue, frames: number, startFrame: number, onQuantum?: (frame: number) => void) {
    const out: Float32Array[] = []
    for (let f = startFrame; f < startFrame + frames; f += Q) {
      onQuantum?.(f)
      const block = new Float32Array(Q)
      queue.process(block, f)
      out.push(block)
    }
    return concat(out)
  }

  it("waits for the jitter lead, then fades in", () => {
    const q = new PcmPlayoutQueue({ sampleRate: RATE })
    q.push(new Float32Array(RATE).fill(0.5), 0)
    const out = run(q, RATE / 2, 0)
    const lead = Math.round(0.12 * RATE)
    expect(maxJump(out, 1, lead)).toBe(0)
    expect(out[lead - 1]).toBe(0)
    expect(out[lead + 2]).toBeGreaterThan(0)
    expect(out[lead + 2]).toBeLessThan(0.01)
    expect(maxJump(out)).toBeLessThan(0.5 / 100)
    expect(out[lead + 400]).toBeCloseTo(0.5, 5)
  })

  it("underrun: fades out, plays silence, re-primes with a longer lead, fades in", () => {
    const q = new PcmPlayoutQueue({ sampleRate: RATE })
    q.push(new Float32Array(RATE * 0.2).fill(0.5), 0)
    const latePush = Math.round(RATE * 0.47)
    const pushes = new Map<number, number>([
      [Math.round(RATE * 0.1), RATE * 0.1],
      // Queue runs dry at 0.42 s; the next chunk of the same reply is 50 ms late.
      [latePush, RATE * 0.2],
    ])
    const out = run(q, RATE, 0, (frame) => {
      for (const [at, len] of pushes) {
        if (frame >= at) {
          q.push(new Float32Array(len).fill(0.5), frame)
          pushes.delete(at)
        }
      }
    })
    expect(q.underruns).toBe(1)
    // No hard edge anywhere: every transition is a ramp.
    expect(maxJump(out)).toBeLessThan(0.5 / 100)
    // There is a silent gap, and the restart waited the grown lead (180 ms).
    const firstEnd = out.findIndex((v, i) => i > RATE * 0.12 && v === 0)
    expect(firstEnd).toBeGreaterThan(RATE * 0.41)
    const restart = out.findIndex((v, i) => i > firstEnd && v !== 0)
    expect(restart - latePush).toBeGreaterThanOrEqual(Math.round(0.18 * RATE) - Q)
    expect(restart - latePush).toBeLessThanOrEqual(Math.round(0.18 * RATE) + 2 * Q)
  })

  it("flush fades out over ~12 ms and drops the rest", () => {
    const q = new PcmPlayoutQueue({ sampleRate: RATE })
    q.push(new Float32Array(RATE).fill(0.5), 0)
    let flushedAt = -1
    const out = run(q, RATE / 2, 0, (frame) => {
      if (flushedAt < 0 && frame >= RATE * 0.25) {
        q.flush()
        flushedAt = frame
      }
    })
    expect(maxJump(out)).toBeLessThan(0.5 / 100)
    const fade = Math.round(0.012 * RATE)
    expect(out[flushedAt]).toBeGreaterThan(0.45)
    expect(out[flushedAt + fade]).toBe(0)
    expect(rms(out, flushedAt + fade)).toBe(0)
    expect(q.isActive()).toBe(false)
  })

  it("audio pushed right after a flush starts a fresh reply", () => {
    const q = new PcmPlayoutQueue({ sampleRate: RATE })
    q.push(new Float32Array(RATE).fill(0.5), 0)
    run(q, RATE * 0.2, 0)
    q.flush()
    q.push(new Float32Array(RATE).fill(-0.25), Math.round(RATE * 0.2))
    expect(q.underruns).toBe(0)
    const out = run(q, RATE * 0.5, Math.round(RATE * 0.2))
    expect(maxJump(out)).toBeLessThan(0.5 / 100)
    expect(out[out.length - 1]).toBeCloseTo(-0.25, 5)
  })
})

describe("pcm-player worklet processor", () => {
  type Registered = new (options?: unknown) => {
    port: { onmessage: ((e: { data: unknown }) => void) | null; postMessage: (m: unknown) => void }
    process: (inputs: unknown[], outputs: Float32Array[][]) => boolean
  }
  const g = globalThis as Record<string, unknown>
  const registered: Record<string, Registered> = {}
  const saved: Record<string, unknown> = {}

  beforeAll(async () => {
    for (const k of ["AudioWorkletProcessor", "registerProcessor", "sampleRate", "currentFrame"]) saved[k] = g[k]
    g.AudioWorkletProcessor = class {
      port = { onmessage: null, postMessage: () => {} }
    }
    g.registerProcessor = (name: string, cls: Registered) => {
      registered[name] = cls
    }
    g.sampleRate = 44100
    g.currentFrame = 0
    await import("@/public/voice-worklets/pcm-player-processor.js")
  })

  afterAll(() => {
    for (const k of Object.keys(saved)) g[k] = saved[k]
  })

  it("plays 24 kHz chunks on a 44.1 kHz context without boundary clicks", () => {
    const Proc = registered["gravitre-pcm-player"]
    expect(Proc).toBeDefined()
    const proc = new Proc({ processorOptions: {} })
    const source = floatArrayToInt16(tone(440, 24000, 24000))
    const out: Float32Array[] = []
    let next = 0
    for (let frame = 0; frame < 44100 * 1.3; frame += 128) {
      g.currentFrame = frame
      // One 40 ms chunk (odd sample count on purpose) every 40 ms of output.
      while (next < source.length && frame >= (next / 24000) * 44100) {
        const chunk = source.slice(next, next + 961)
        proc.port.onmessage?.({ data: { type: "pcm", pcm: chunk, sampleRate: 24000 } })
        next += 961
      }
      const block = new Float32Array(128)
      proc.process([], [[block]])
      out.push(block)
    }
    const all = concat(out)
    const lead = Math.round(0.12 * 44100)
    const expected = 2 * Math.PI * 440 * 0.5 / 44100
    expect(maxJump(all, lead + 300, lead + 44100 - 300)).toBeLessThan(expected * 1.1)
  })
})
