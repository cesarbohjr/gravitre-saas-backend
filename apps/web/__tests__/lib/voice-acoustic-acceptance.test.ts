import { afterEach, describe, expect, it, vi } from "vitest"
import { createAcousticAcceptanceCapture } from "@/lib/voice-acoustic-acceptance"

describe("explicit local acoustic acceptance capture", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("records post-duck output and timing only after explicit start", async () => {
    const stopTrack = vi.fn()
    const stream = { getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream
    const stateListeners = new Set<() => void>()
    const ctx = {
      currentTime: 0.4, sampleRate: 48000, state: "running",
      createMediaStreamDestination: () => ({ stream }),
      addEventListener: (_type: string, callback: () => void) => stateListeners.add(callback),
      removeEventListener: (_type: string, callback: () => void) => stateListeners.delete(callback),
    } as unknown as AudioContext

    class Recorder {
      static isTypeSupported = (mime: string) => mime === "audio/webm;codecs=opus"
      mimeType = "audio/webm;codecs=opus"
      state: RecordingState = "inactive"
      ondataavailable: ((event: { data: Blob }) => void) | null = null
      private listeners: Record<string, Array<() => void>> = {}
      constructor(_stream: MediaStream, _options?: MediaRecorderOptions) {}
      start() { this.state = "recording" }
      addEventListener(type: string, callback: () => void) {
        ;(this.listeners[type] ??= []).push(callback)
      }
      stop() {
        this.state = "inactive"
        this.ondataavailable?.({ data: new Blob(["acoustic fixture"]) })
        for (const listener of this.listeners.stop ?? []) listener()
      }
    }
    vi.stubGlobal("MediaRecorder", Recorder)
    const capture = createAcousticAcceptanceCapture(ctx)
    // No implicit recorder activity or observations.
    capture.onAcousticTiming({ event: "duck", monotonic_ms: 1, audio_context_s: 0.1 })
    capture.start()
    capture.onAcousticTiming({ event: "pcm_enqueue", monotonic_ms: 10, audio_context_s: 0.4, pcm_frames: 960, pcm_sample_rate: 24000 })
    capture.onAcousticTiming({ event: "duck", monotonic_ms: 20, audio_context_s: 0.42 })
    const { audio, manifest } = await capture.stop()
    expect(audio.size).toBeGreaterThan(0)
    expect(manifest.captured_audio_kind).toBe("post_duck_browser_stream")
    expect(manifest.observations.map((event) => event.event)).toEqual(["context_state", "pcm_enqueue", "duck"])
    expect(manifest.limits.browser_stream_not_physical_speaker).toBe(true)
    expect(manifest.limits.provider_tts_generation_times_not_measured).toBe(true)
    expect(stateListeners.size).toBe(0)
    capture.dispose()
    expect(stopTrack).toHaveBeenCalled()
  })

  it("does not silently restart an active recording", () => {
    const ctx = {
      currentTime: 0, sampleRate: 48000, state: "running",
      createMediaStreamDestination: () => ({ stream: { getTracks: () => [] } }),
      addEventListener() {}, removeEventListener() {},
    } as unknown as AudioContext
    class Recorder {
      static isTypeSupported = () => true
      state: RecordingState = "inactive"
      ondataavailable = null
      constructor(_stream: MediaStream, _opts?: MediaRecorderOptions) {}
      start() { this.state = "recording" }
      stop() { this.state = "inactive" }
    }
    vi.stubGlobal("MediaRecorder", Recorder)
    const capture = createAcousticAcceptanceCapture(ctx)
    capture.start()
    expect(() => capture.start()).toThrow("already started")
    capture.dispose()
  })
})
