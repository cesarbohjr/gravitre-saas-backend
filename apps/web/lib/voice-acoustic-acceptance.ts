/**
 * Explicit user-consented browser acoustic acceptance capture.
 *
 * This module has no persistent storage, network calls or implicit activation.
 * The caller must invoke start() after a user gesture and pass the outputTap
 * and onAcousticTiming into createVoicePcmPlayer's options. The resulting Blob
 * is post-duck browser output, not a physical microphone/speaker recording.
 * For a speaker-level verdict, use a separately consented external recording.
 */
import type { AcousticTimingEvent } from "@/lib/voice-pcm-player"

export type AcousticAcceptanceManifest = {
  schema: "gravitre.acoustic-acceptance.v1"
  captured_audio_kind: "post_duck_browser_stream"
  started_monotonic_ms: number
  duration_ms: number
  mime_type: string
  audio_context_sample_rate: number
  observations: Array<AcousticTimingEvent | {
    event: "context_state"
    monotonic_ms: number
    audio_context_s: number
    state: string
  }>
  limits: {
    observations_truncated: boolean
    browser_stream_not_physical_speaker: true
    provider_tts_generation_times_not_measured: true
  }
}

const MAX_OBSERVATIONS = 12000

export function createAcousticAcceptanceCapture(ctx: AudioContext) {
  const output = ctx.createMediaStreamDestination()
  let recorder: MediaRecorder | null = null
  let startedAt: number | null = null
  let records: AcousticAcceptanceManifest["observations"] = []
  let blobs: Blob[] = []
  let truncated = false

  const record = (entry: AcousticAcceptanceManifest["observations"][number]) => {
    if (startedAt === null) return
    if (records.length >= MAX_OBSERVATIONS) { truncated = true; return }
    records.push(entry)
  }
  const onContextState = () => record({
    event: "context_state",
    monotonic_ms: performance.now(),
    audio_context_s: ctx.currentTime,
    state: ctx.state,
  })

  return {
    /** Connect to VoicePcmPlayerOptions.acceptanceOutputTap. */
    outputTap: output as AudioNode,
    /** Connect to VoicePcmPlayerOptions.onAcousticTiming. */
    onAcousticTiming: (observation: AcousticTimingEvent) => record(observation),
    start() {
      if (startedAt !== null) throw new Error("Acoustic capture already started")
      if (typeof MediaRecorder === "undefined") throw new Error("MediaRecorder is unavailable")
      const selected = ["audio/webm;codecs=opus", "audio/mp4", ""]
        .find((mime) => !mime || MediaRecorder.isTypeSupported(mime))
      if (selected === undefined) throw new Error("No supported audio recorder")
      recorder = selected ? new MediaRecorder(output.stream, { mimeType: selected }) : new MediaRecorder(output.stream)
      records = []
      blobs = []
      truncated = false
      recorder.ondataavailable = (event) => { if (event.data.size) blobs.push(event.data) }
      startedAt = performance.now()
      ctx.addEventListener("statechange", onContextState)
      onContextState()
      recorder.start(1000)
    },
    async stop(): Promise<{ audio: Blob; manifest: AcousticAcceptanceManifest }> {
      const current = recorder
      if (!current || startedAt === null) throw new Error("No active acoustic capture")
      if (current.state === "inactive") throw new Error("Recorder was already stopped")
      const began = startedAt
      const ended = performance.now()
      ctx.removeEventListener("statechange", onContextState)
      await new Promise<void>((resolve, reject) => {
        current.addEventListener("stop", () => resolve(), { once: true })
        current.addEventListener("error", () => reject(new Error("Acoustic recording failed")), { once: true })
        current.stop()
      })
      const mime = current.mimeType || "application/octet-stream"
      const audio = new Blob(blobs, { type: mime })
      const manifest: AcousticAcceptanceManifest = {
        schema: "gravitre.acoustic-acceptance.v1",
        captured_audio_kind: "post_duck_browser_stream",
        started_monotonic_ms: began,
        duration_ms: Math.max(0, ended - began),
        mime_type: mime,
        audio_context_sample_rate: ctx.sampleRate,
        observations: records.slice(),
        limits: {
          observations_truncated: truncated,
          browser_stream_not_physical_speaker: true,
          provider_tts_generation_times_not_measured: true,
        },
      }
      startedAt = null
      recorder = null
      return { audio, manifest }
    },
    dispose() {
      ctx.removeEventListener("statechange", onContextState)
      if (recorder?.state === "recording") recorder.stop()
      recorder = null
      startedAt = null
      for (const track of output.stream.getTracks()) track.stop()
    },
  }
}
