import { readFileSync } from "node:fs"
import { join } from "node:path"

import { afterEach, describe, expect, it, vi } from "vitest"

import {
  assistantTextKind,
  createPlaybackProgressTracker,
  encodePlaybackProgress,
  transcriptDisposition,
} from "@/lib/voice-playback-progress"
import {
  PLAYED_EXTRAPOLATION_MAX_S,
  createBufferSourcePcmPlayer,
  createWorkletPcmPlayer,
} from "@/lib/voice-pcm-player"

describe("playback progress tracker", () => {
  it("reports played ms per reply on the shared player timeline", () => {
    const t = createPlaybackProgressTracker()
    t.noteReceived(3, 16000, 16000) // reply 3: 1.0 s
    const mid = t.reports(0.4, { reason: "periodic" })
    expect(mid).toEqual([
      {
        type: "playback.progress",
        reply_id: 3,
        received_ms: 1000,
        played_ms: 400,
        interrupted: false,
        final: false,
        reason: "periodic",
      },
    ])
    // Never claims more than was received.
    expect(t.reports(5, { reason: "periodic" })[0].played_ms).toBe(1000)
  })

  it("starts a newer reply where the older one's audio ends and finalises the older", () => {
    const t = createPlaybackProgressTracker()
    t.noteReceived(1, 8000, 16000) // 0.5 s
    t.noteReceived(2, 16000, 16000) // 1.0 s, queued after reply 1
    const reports = t.reports(0.8, { reason: "periodic" })
    // Reply 1 is final (newer audio arrived), so only reply 2 is reported.
    expect(reports.map((r) => [r.reply_id, r.played_ms])).toEqual([[2, 300]])
  })

  it("finalises on interruption and does not report the same reply twice", () => {
    const t = createPlaybackProgressTracker()
    t.noteReceived(4, 16000, 16000)
    const cut = t.reports(0.25, { reason: "interrupted", interrupted: true })
    expect(cut).toHaveLength(1)
    expect(cut[0]).toMatchObject({ reply_id: 4, played_ms: 250, interrupted: true, final: true })
    expect(t.hasOpenReplies()).toBe(false)
    t.reset()
    expect(t.reports(0, { reason: "barge_in", interrupted: true })).toEqual([])
  })

  it("reports an interrupted reply whose audio never arrived as played 0", () => {
    const t = createPlaybackProgressTracker()
    const reports = t.reports(0, { reason: "interrupted", interrupted: true, ensureReplyId: 7 })
    expect(reports).toEqual([expect.objectContaining({ reply_id: 7, played_ms: 0, received_ms: 0 })])
  })

  it("ignores frames without a reply id and restarts the timeline on reset", () => {
    const t = createPlaybackProgressTracker()
    t.noteReceived(undefined, 16000, 16000)
    t.noteReceived("2", 16000, 16000)
    expect(t.hasOpenReplies()).toBe(false)
    t.noteReceived(5, 16000, 16000)
    t.reset() // flush: open entries are dropped, the timeline restarts
    t.noteReceived(6, 8000, 16000)
    expect(t.reports(0.2, { reason: "periodic" }).map((r) => [r.reply_id, r.played_ms])).toEqual([[6, 200]])
  })

  it("encodes as the JSON message the server routes", () => {
    const t = createPlaybackProgressTracker()
    t.noteReceived(1, 1600, 16000)
    const wire = JSON.parse(encodePlaybackProgress(t.reports(0.1, { reason: "drained" })[0]))
    expect(wire).toMatchObject({ type: "playback.progress", reply_id: 1, played_ms: 100, reason: "drained" })
  })
})

describe("transcript disposition and assistant text kind", () => {
  it("keeps backchannel finals out of the turn path", () => {
    expect(transcriptDisposition({ final: true, backchannel: true })).toBe("backchannel")
    expect(transcriptDisposition({ final: true })).toBe("final")
    expect(transcriptDisposition({ final: false, backchannel: true })).toBe("interim")
  })

  it("treats unlabelled text as answer", () => {
    expect(assistantTextKind({ kind: "filler" })).toBe("filler")
    expect(assistantTextKind({ kind: "progress" })).toBe("progress")
    expect(assistantTextKind({ kind: "answer" })).toBe("answer")
    expect(assistantTextKind({})).toBe("answer")
  })
})

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
  const ctx = { currentTime: 0, sampleRate: 48000, destination: {} } as unknown as AudioContext & {
    currentTime: number
  }
  const emit = (data: unknown) => port.onmessage?.({ data } as MessageEvent)
  return { ctx, posted, emit }
}

describe("worklet player playedSeconds", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("follows progress reports, extrapolates briefly, and caps at what was posted", () => {
    const { ctx, emit } = fakeWorkletEnv()
    const player = createWorkletPcmPlayer(ctx)
    player.enqueue(new Int16Array(24000), 24000) // 1.0 s posted
    emit({ type: "active", active: true, seq: 1 })
    emit({ type: "progress", epoch: 0, played: 24000, frame: 48000 }) // 0.5 s at t=1.0
    ctx.currentTime = 1.02
    expect(player.playedSeconds()).toBeCloseTo(0.52, 5)
    ctx.currentTime = 3
    expect(player.playedSeconds()).toBeCloseTo(0.5 + PLAYED_EXTRAPOLATION_MAX_S, 5)
    emit({ type: "progress", epoch: 0, played: 96000, frame: 144000 })
    expect(player.playedSeconds()).toBe(1)
  })

  it("restarts at a flush and ignores progress from the previous epoch", () => {
    const { ctx, emit, posted } = fakeWorkletEnv()
    const player = createWorkletPcmPlayer(ctx)
    player.enqueue(new Int16Array(24000), 24000)
    emit({ type: "progress", epoch: 0, played: 24000, frame: 0 })
    player.flush()
    expect(posted).toContainEqual({ type: "flush", epoch: 1 })
    expect(player.playedSeconds()).toBe(0)
    emit({ type: "progress", epoch: 0, played: 48000, frame: 0 }) // stale
    expect(player.playedSeconds()).toBe(0)
    player.enqueue(new Int16Array(24000), 24000)
    emit({ type: "progress", epoch: 1, played: 4800, frame: 0 })
    expect(player.playedSeconds()).toBeCloseTo(0.1, 5)
  })
})

function fakeBufferSourceCtx() {
  const starts: number[] = []
  const gain = () => ({
    gain: { value: 1, setValueAtTime() {}, linearRampToValueAtTime() {} },
    connect() {},
    disconnect() {},
  })
  const ctx = {
    currentTime: 0,
    sampleRate: 16000,
    destination: {},
    createGain: gain,
    createBuffer: (_c: number, length: number) => ({ length, copyToChannel() {} }),
    createBufferSource: () => ({
      buffer: null,
      onended: null,
      connect() {},
      start: (at: number) => starts.push(at),
      stop() {},
    }),
  }
  return { ctx: ctx as unknown as AudioContext & { currentTime: number }, starts }
}

describe("buffer-source player playedSeconds", () => {
  it("counts only scheduled audio the clock has passed, and restarts at a flush", () => {
    vi.useFakeTimers()
    try {
      const { ctx, starts } = fakeBufferSourceCtx()
      const player = createBufferSourcePcmPlayer(ctx)
      player.enqueue(new Int16Array(16000), 16000)
      const start = starts[0]
      expect(player.playedSeconds()).toBe(0)
      ctx.currentTime = start + 0.25
      expect(player.playedSeconds()).toBeCloseTo(0.25, 2)
      ctx.currentTime = start + 5 // long past the end: never more than scheduled
      const total = player.playedSeconds()
      expect(total).toBeGreaterThan(0.9)
      expect(total).toBeLessThanOrEqual(1.0001)
      player.flush()
      expect(player.playedSeconds()).toBe(0)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe("duplex hook playback wiring", () => {
  const src = readFileSync(join(__dirname, "../../hooks/use-voice-duplex-session.ts"), "utf8")

  it("returns on a backchannel final before resetting the reply", () => {
    const at = src.indexOf('if (disposition === "backchannel")')
    expect(at).toBeGreaterThan(0)
    const block = src.slice(at, src.indexOf('if (disposition === "final")', at))
    expect(block).toContain("onBackchannel")
    expect(block).toContain("return")
    expect(block).not.toContain("onUserFinal")
    expect(block).not.toContain("assistantTextRef.current = \"\"")
  })

  it("reports the cut position before the player is flushed", () => {
    const serverCut = src.indexOf('sendPlaybackProgress("interrupted"')
    expect(serverCut).toBeGreaterThan(0)
    const bargeIn = src.indexOf('sendPlaybackProgress("barge_in"')
    expect(bargeIn).toBeGreaterThan(0)
    expect(src.indexOf("stopPlayback()", bargeIn)).toBeGreaterThan(bargeIn)
    expect(src.slice(bargeIn, src.indexOf("stopPlayback()", bargeIn))).not.toContain("flush")
  })

  it("only reports when session.ready turns playback-grounded history on", () => {
    expect(src).toContain("playbackReportsEnabledRef.current = msg.playback_grounded_history_v1 === true")
    expect(src).toMatch(/if \(!playbackReportsEnabledRef\.current \|\| orchestrationRef\.current !== "pipecat"\) return/)
  })
})
