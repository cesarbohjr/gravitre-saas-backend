/**
 * AudioWorklet microphone capture for voice. Replaces the main-thread
 * ScriptProcessorNode: audio is collected on the audio thread, so a busy main
 * thread delays blocks instead of dropping them, and it is resampled to the
 * wire rate with a band-limited filter (no aliasing, no block-edge phase jumps).
 *
 * Posts { raw: Float32Array (context rate), pcm: Float32Array (target rate) }
 * every `blockFrames` input frames, matching the old 4096-frame callback.
 */
import { StreamingResampler } from "./voice-dsp.js"

class GravitreMicCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super()
    const opts = (options && options.processorOptions) || {}
    this.blockFrames = Number(opts.blockFrames) || 4096
    this.resampler = new StreamingResampler(sampleRate, Number(opts.targetRate) || 16000)
    this.raw = new Float32Array(this.blockFrames)
    this.rawLen = 0
    this.disposed = false
    this.port.onmessage = (event) => {
      if (event.data && event.data.type === "dispose") this.disposed = true
    }
  }

  process(inputs) {
    if (this.disposed) return false
    const input = inputs[0] && inputs[0][0]
    if (!input) return true
    let offset = 0
    while (offset < input.length) {
      const take = Math.min(input.length - offset, this.blockFrames - this.rawLen)
      this.raw.set(input.subarray(offset, offset + take), this.rawLen)
      this.rawLen += take
      offset += take
      if (this.rawLen === this.blockFrames) {
        const raw = this.raw
        const pcm = this.resampler.process(raw)
        this.port.postMessage({ raw, pcm }, [raw.buffer, pcm.buffer])
        this.raw = new Float32Array(this.blockFrames)
        this.rawLen = 0
      }
    }
    return true
  }
}

registerProcessor("gravitre-mic-capture", GravitreMicCaptureProcessor)
