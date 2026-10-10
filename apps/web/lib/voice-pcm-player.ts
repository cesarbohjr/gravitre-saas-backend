/**
 * Streamed voice PCM playback (Pipecat replies).
 *
 * Preferred: an AudioWorklet player (public/voice-worklets/pcm-player-processor.js)
 * that resamples the reply as one continuous stream and plays it from a queue on
 * the audio thread, with fades on underrun and on flush.
 *
 * Fallback (no AudioWorklet): scheduled AudioBufferSourceNodes, but resampled
 * here to the context rate and scheduled on an integer frame cursor. Creating
 * each 24 kHz chunk as its own AudioBuffer and letting the browser resample it
 * is what clicked: Chromium resamples every buffer on its own, and on a
 * 44.1 kHz context each buffer's last output frame overlapped the next
 * buffer's first, doubling one sample at every 40 ms boundary.
 */

import {
  StreamingResampler,
  int16ArrayToFloat,
} from "@/public/voice-worklets/voice-dsp.js"
import { createPcmJitterState, schedulePcmStart } from "@/lib/voice-pcm-jitter"
import { VOICE_PCM_PLAYER_PROCESSOR, loadVoiceWorklets } from "@/lib/voice-worklets"

/** Fade applied when playback is cut (barge-in, stop), instead of a hard stop. */
export const PCM_FLUSH_FADE_S = 0.012

export type VoicePcmPlayerKind = "worklet" | "buffer-source"

export type VoicePcmPlayerOptions = {
  /** Where audio goes; defaults to ctx.destination. */
  destination?: AudioNode
  /** Audible playback started (first frame of a reply, or after an underrun). */
  onStarted?: (ctxTime: number) => void
  /** Whether anything is queued or playing changed. */
  onActiveChange?: (active: boolean) => void
}

export type VoicePcmPlayer = {
  readonly kind: VoicePcmPlayerKind
  /** Queue PCM16 mono. Throws if the browser refuses to schedule it. */
  enqueue: (pcm: Int16Array, sampleRate: number) => void
  /** Fade out and drop everything queued (barge-in). */
  flush: () => void
  isActive: () => boolean
  /** Context time the first audio since the last flush started at, if any. */
  originTime: () => number | null
  /**
   * Seconds of reply audio actually played since the last flush: real audio
   * only, never underrun gaps or the flush fade. Feeds the per-reply
   * playback.progress reports the server uses to cut history to what was heard.
   */
  playedSeconds: () => number
  dispose: () => void
}

/** Most a worklet player extrapolates past its last progress report (s). */
export const PLAYED_EXTRAPOLATION_MAX_S = 0.1

export async function createVoicePcmPlayer(
  ctx: AudioContext,
  options: VoicePcmPlayerOptions = {},
): Promise<VoicePcmPlayer> {
  if (await loadVoiceWorklets(ctx)) {
    try {
      return createWorkletPcmPlayer(ctx, options)
    } catch (err) {
      if (typeof console !== "undefined") {
        console.warn("[gravitre-voice] PCM worklet player failed, using fallback", err)
      }
    }
  }
  return createBufferSourcePcmPlayer(ctx, options)
}

/** Requires loadVoiceWorklets(ctx) to have resolved true. */
export function createWorkletPcmPlayer(
  ctx: AudioContext,
  options: VoicePcmPlayerOptions = {},
): VoicePcmPlayer {
  const node = new AudioWorkletNode(ctx, VOICE_PCM_PLAYER_PROCESSOR, {
    numberOfInputs: 0,
    numberOfOutputs: 1,
    outputChannelCount: [1],
    processorOptions: { flushFadeS: PCM_FLUSH_FADE_S },
  })
  node.connect(options.destination ?? ctx.destination)
  let active = false
  let origin: number | null = null
  // Sequence of the last pcm message posted; the worklet echoes the last one it
  // processed. An "inactive" report from before audio we already posted (e.g. the
  // end of a barge-in flush fade) is stale and must not end the reply.
  let posted = 0
  // Played-audio accounting, per flush epoch (the worklet restarts its count
  // at each flush and tags reports with the epoch it belongs to).
  let epoch = 0
  let playedFrames = 0
  let progressAt: number | null = null
  let postedSeconds = 0
  node.port.onmessage = (event: MessageEvent) => {
    const msg = event.data as {
      type?: string
      active?: boolean
      frame?: number
      seq?: number
      epoch?: number
      played?: number
    }
    if (msg?.type === "progress") {
      if (msg.epoch !== epoch || typeof msg.played !== "number") return
      playedFrames = Math.max(playedFrames, msg.played)
      progressAt = typeof msg.frame === "number" ? msg.frame / ctx.sampleRate : ctx.currentTime
      return
    }
    if (msg?.type === "started") {
      const at = typeof msg.frame === "number" ? msg.frame / ctx.sampleRate : ctx.currentTime
      if (origin == null) origin = at
      options.onStarted?.(at)
    } else if (msg?.type === "active") {
      const next = Boolean(msg.active)
      if (!next && typeof msg.seq === "number" && msg.seq < posted) return
      if (next === active) return
      active = next
      options.onActiveChange?.(next)
    }
  }
  return {
    kind: "worklet",
    enqueue(pcm, sampleRate) {
      if (pcm.length === 0) return
      // Copy so the caller's buffer survives the transfer.
      const copy = new Int16Array(pcm)
      if (!active) {
        active = true
        // Until the worklet reports the real start, assume the initial lead.
        if (origin == null) origin = ctx.currentTime + 0.12
        options.onActiveChange?.(true)
      }
      posted += 1
      postedSeconds += pcm.length / (sampleRate || 16000)
      node.port.postMessage(
        { type: "pcm", pcm: copy, sampleRate: sampleRate || 16000, seq: posted },
        [copy.buffer],
      )
    },
    flush() {
      epoch += 1
      playedFrames = 0
      progressAt = null
      postedSeconds = 0
      node.port.postMessage({ type: "flush", epoch })
      origin = null
    },
    isActive: () => active,
    originTime: () => origin,
    playedSeconds() {
      let seconds = playedFrames / ctx.sampleRate
      if (active && progressAt != null) {
        // Between reports (~50 ms apart) assume playback kept going, briefly.
        seconds += Math.min(PLAYED_EXTRAPOLATION_MAX_S, Math.max(0, ctx.currentTime - progressAt))
      }
      return Math.max(0, Math.min(postedSeconds, seconds))
    },
    dispose() {
      try {
        node.port.postMessage({ type: "dispose" })
        node.port.onmessage = null
        node.disconnect()
      } catch {
        /* ignore */
      }
    },
  }
}

/** AudioBufferSourceNode fallback for browsers without AudioWorklet. */
export function createBufferSourcePcmPlayer(
  ctx: AudioContext,
  options: VoicePcmPlayerOptions = {},
): VoicePcmPlayer {
  const destination = options.destination ?? ctx.destination
  const rate = ctx.sampleRate
  let out = ctx.createGain()
  out.connect(destination)
  let sources: AudioBufferSourceNode[] = []
  let resampler: StreamingResampler | null = null
  let jitter = createPcmJitterState()
  /** Next start position in output frames; integer so chunks abut exactly. */
  let nextFrame = 0
  let origin: number | null = null
  let fadeInPending = true
  const fadeFrames = Math.max(1, Math.round(0.004 * rate))
  // Buffers scheduled since the last flush, for playedSeconds(); fully played
  // ones are folded into playedDoneS.
  let scheduled: Array<{ start: number; dur: number }> = []
  let playedDoneS = 0

  const setActive = (next: boolean) => options.onActiveChange?.(next)

  return {
    kind: "buffer-source",
    enqueue(pcm, sampleRate) {
      if (pcm.length === 0) return
      const inRate = sampleRate || 16000
      if (!resampler || resampler.inRate !== inRate) resampler = new StreamingResampler(inRate, rate)
      const samples = resampler.process(int16ArrayToFloat(pcm))
      if (samples.length === 0) return
      const startAt = schedulePcmStart(jitter, ctx.currentTime, nextFrame / rate, performance.now())
      const startFrame = Math.round(startAt * rate)
      if (startFrame !== nextFrame) fadeInPending = true
      if (fadeInPending) {
        // Restarting after a gap: ramp in rather than jump to mid-waveform.
        const n = Math.min(fadeFrames, samples.length)
        for (let i = 0; i < n; i++) samples[i] *= (i + 1) / (n + 1)
        fadeInPending = false
      }
      const buf = ctx.createBuffer(1, samples.length, rate)
      buf.copyToChannel(samples, 0)
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(out)
      src.start(startFrame / rate)
      scheduled.push({ start: startFrame / rate, dur: samples.length / rate })
      if (origin == null) origin = startFrame / rate
      nextFrame = startFrame + samples.length
      if (sources.length === 0) setActive(true)
      sources.push(src)
      options.onStarted?.(startFrame / rate)
      src.onended = () => {
        const before = sources.length
        sources = sources.filter((s) => s !== src)
        if (before > 0 && sources.length === 0) setActive(false)
      }
    },
    flush() {
      const old = out
      const oldSources = sources
      const now = ctx.currentTime
      try {
        old.gain.setValueAtTime(old.gain.value, now)
        old.gain.linearRampToValueAtTime(0, now + PCM_FLUSH_FADE_S)
      } catch {
        /* ignore */
      }
      for (const src of oldSources) {
        src.onended = null
        try {
          src.stop(now + PCM_FLUSH_FADE_S + 0.005)
        } catch {
          /* ignore */
        }
      }
      setTimeout(() => {
        try {
          old.disconnect()
        } catch {
          /* ignore */
        }
      }, (PCM_FLUSH_FADE_S + 0.05) * 1000)
      out = ctx.createGain()
      out.connect(destination)
      const wasActive = oldSources.length > 0
      sources = []
      resampler?.reset()
      jitter = createPcmJitterState()
      nextFrame = 0
      origin = null
      fadeInPending = true
      scheduled = []
      playedDoneS = 0
      if (wasActive) setActive(false)
    },
    isActive: () => sources.length > 0,
    originTime: () => origin,
    playedSeconds() {
      const now = ctx.currentTime
      let partial = 0
      const pending: Array<{ start: number; dur: number }> = []
      for (const item of scheduled) {
        const elapsed = now - item.start
        if (elapsed >= item.dur) playedDoneS += item.dur
        else {
          if (elapsed > 0) partial += elapsed
          pending.push(item)
        }
      }
      scheduled = pending
      return playedDoneS + partial
    },
    dispose() {
      for (const src of sources) {
        src.onended = null
        try {
          src.stop()
        } catch {
          /* ignore */
        }
      }
      sources = []
      try {
        out.disconnect()
      } catch {
        /* ignore */
      }
    },
  }
}

