/**
 * Browser side of the playback-continuity harness (SYNTHETIC signal, synthetic
 * network jitter). Bundled by run.mjs; drives the real player code.
 *
 * "before": the pre-change enqueuePcm logic from use-voice-duplex-session.ts,
 *   kept verbatim in shape: one AudioBufferSourceNode per message created at
 *   the source rate, scheduled with the real schedulePcmStart, each message
 *   decoded on its own with base64ToPcm16, flush = src.stop().
 * "after": createVoicePcmPlayer (AudioWorklet player) + createPcm16StreamDecoder.
 */
import { base64ToPcm16, createPcm16StreamDecoder } from "@/lib/pipecat-voice-client"
import { createPcmJitterState, schedulePcmStart } from "@/lib/voice-pcm-jitter"
import { createVoicePcmPlayer } from "@/lib/voice-pcm-player"

type Impl = "before" | "after"
export type Scenario = {
  impl: Impl
  ctxRate: number
  seed: number
  oddSplit: boolean
  replyS: number
  flushAtS: number
  secondReplyDelayS: number
  secondReplyS: number
  jitterMaxMs: number
  /** Server send rate relative to real time (Pipecat 1.x: 2; a real-time-bound TTS: 1). */
  pacing: number
}

const SRC_RATE = 24000

function rng(seed: number) {
  let s = seed >>> 0 || 1
  return () => {
    s ^= s << 13
    s ^= s >>> 17
    s ^= s << 5
    return (s >>> 0) / 4294967296
  }
}

/** Smooth, never-zero speech-like test signal (sum of harmonics, slow AM). */
export function signalAt(t: number, reply: number): number {
  const f0 = reply === 0 ? 180 : 210
  const env = 0.6 + 0.4 * Math.sin(2 * Math.PI * 1.3 * t)
  return 0.5 * env * (0.6 * Math.sin(2 * Math.PI * f0 * t) + 0.3 * Math.sin(2 * Math.PI * 2 * f0 * t + 0.4) + 0.1 * Math.sin(2 * Math.PI * 4 * f0 * t + 1.1))
}

function makeReplyBytes(seconds: number, reply: number): Uint8Array {
  const n = Math.round(seconds * SRC_RATE)
  const pcm = new Int16Array(n)
  for (let i = 0; i < n; i++) pcm[i] = Math.round(signalAt(i / SRC_RATE, reply) * 32767)
  return new Uint8Array(pcm.buffer)
}

function toB64(bytes: Uint8Array): string {
  let s = ""
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(s)
}

/** Split into server messages: 40 ms (1920 B) like Pipecat, or random odd lengths. */
function packetize(bytes: Uint8Array, odd: boolean, rand: () => number): Uint8Array[] {
  const out: Uint8Array[] = []
  let at = 0
  while (at < bytes.length) {
    let len = 1920
    if (odd) len = 2 * Math.floor(150 + rand() * 1350) + 1
    out.push(bytes.subarray(at, Math.min(bytes.length, at + len)))
    at += len
  }
  return out
}

const RECORDER = `
class TapRecorder extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(8192); this.len = 0; this.on = true;
    this.port.onmessage = (e) => { if (e.data === 'stop') { this.flush(); this.on = false; this.port.postMessage({ done: true }) } } }
  flush() { if (this.len) { this.port.postMessage({ chunk: this.buf.slice(0, this.len) }); this.len = 0 } }
  process(inputs, outputs) {
    const x = inputs[0] && inputs[0][0]
    const n = outputs[0][0].length
    for (let i = 0; i < n; i++) { const v = x ? x[i] : 0; if (this.on) { this.buf[this.len++] = v; if (this.len === this.buf.length) this.flush() } outputs[0][0][i] = 0 }
    return true
  }
}
registerProcessor('tap-recorder', TapRecorder)
`

type Player = {
  push: (b64: string) => void
  flush: () => void
}

function beforePlayer(ctx: AudioContext, dest: AudioNode): Player {
  let sources: AudioBufferSourceNode[] = []
  let nextTime = 0
  let jitter = createPcmJitterState()
  return {
    push(b64) {
      const pcm = base64ToPcm16(b64)
      if (pcm.length === 0) return
      const f32 = new Float32Array(pcm.length)
      for (let i = 0; i < pcm.length; i++) f32[i] = (pcm[i] ?? 0) / 32768
      const buf = ctx.createBuffer(1, f32.length, SRC_RATE)
      buf.copyToChannel(f32, 0)
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(dest)
      const startAt = schedulePcmStart(jitter, ctx.currentTime, nextTime, performance.now())
      src.start(startAt)
      nextTime = startAt + buf.duration
      sources.push(src)
      src.onended = () => {
        sources = sources.filter((s) => s !== src)
      }
    },
    flush() {
      for (const s of sources) {
        try {
          s.stop()
        } catch {
          /* ignore */
        }
      }
      sources = []
      nextTime = 0
      jitter = createPcmJitterState()
    },
  }
}

async function afterPlayer(ctx: AudioContext, dest: AudioNode): Promise<Player & { kind: string }> {
  const player = await createVoicePcmPlayer(ctx, { destination: dest })
  const decoder = createPcm16StreamDecoder()
  return {
    kind: player.kind,
    push(b64) {
      player.enqueue(decoder.decode(b64), SRC_RATE)
    },
    flush() {
      player.flush()
      decoder.reset()
    },
  }
}

export async function runScenario(sc: Scenario) {
  const ctx = new AudioContext({ sampleRate: sc.ctxRate })
  await ctx.resume()
  const url = URL.createObjectURL(new Blob([RECORDER], { type: "text/javascript" }))
  await ctx.audioWorklet.addModule(url)
  const tap = new AudioWorkletNode(ctx, "tap-recorder", { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] })
  const bus = ctx.createGain()
  bus.connect(tap)
  tap.connect(ctx.destination)
  const chunks: Float32Array[] = []
  const done = new Promise<void>((resolve) => {
    tap.port.onmessage = (e) => {
      if (e.data.chunk) chunks.push(e.data.chunk)
      if (e.data.done) resolve()
    }
  })
  const player = sc.impl === "before" ? beforePlayer(ctx, bus) : await afterPlayer(ctx, bus)
  const rand = rng(sc.seed)
  const t0 = performance.now()
  const recordStartFrame = Math.round(ctx.currentTime * ctx.sampleRate)

  // Server pacing: Pipecat 1.x sends each 40 ms chunk every 20 ms (pacing 2).
  // Network/main-thread delay: uniform 0..jitterMaxMs per message, in order.
  type Msg = { at: number; b64: string; reply: number }
  const msgs: Msg[] = []
  let lastArrival = 0
  const schedule = (bytes: Uint8Array, startMs: number, reply: number, stopAtMs: number) => {
    let sendMs = startMs
    for (const p of packetize(bytes, sc.oddSplit, rand)) {
      if (sendMs >= stopAtMs) break
      const arrival = Math.max(lastArrival, sendMs + rand() * sc.jitterMaxMs)
      lastArrival = arrival
      msgs.push({ at: arrival, b64: toB64(p), reply })
      sendMs += (p.length / 2 / SRC_RATE) * 1000 / sc.pacing
    }
  }
  const flushMs = sc.flushAtS * 1000
  schedule(makeReplyBytes(sc.replyS, 0), 0, 0, flushMs)
  const secondStart = flushMs + sc.secondReplyDelayS * 1000
  lastArrival = secondStart
  schedule(makeReplyBytes(sc.secondReplyS, 1), secondStart, 1, Infinity)

  // Barge-in: the server stops sending reply 0 at the flush; anything already
  // in flight before the flush is delivered before the interrupt message.
  const events: Array<{ at: number; run: () => void }> = msgs.map((m) => ({
    at: m.reply === 0 ? Math.min(m.at, flushMs - 1) : m.at,
    run: () => player.push(m.b64),
  }))
  let flushCtxFrame = -1
  events.push({
    at: flushMs,
    run: () => {
      flushCtxFrame = Math.round(ctx.currentTime * ctx.sampleRate) - recordStartFrame
      player.flush()
    },
  })
  events.sort((a, b) => a.at - b.at)
  for (const ev of events) {
    const wait = ev.at - (performance.now() - t0)
    if (wait > 0) await new Promise((r) => setTimeout(r, wait))
    ev.run()
  }
  const endMs = lastArrival + 1200
  await new Promise((r) => setTimeout(r, Math.max(0, endMs - (performance.now() - t0))))
  tap.port.postMessage("stop")
  await done
  await ctx.close()
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Float32Array(total)
  let o = 0
  for (const c of chunks) {
    out.set(c, o)
    o += c.length
  }
  return {
    samples: Array.from(out),
    sampleRate: sc.ctxRate,
    flushFrame: flushCtxFrame,
    playerKind: "kind" in player ? (player as { kind: string }).kind : "before-buffer-source",
  }
}

;(window as unknown as { runScenario: typeof runScenario }).runScenario = runScenario
;(window as unknown as { harnessReady: boolean }).harnessReady = true
