/**
 * AudioWorklet playback for streamed voice PCM (Pipecat / ElevenLabs).
 *
 * Replaces one AudioBufferSourceNode per 40 ms chunk. Chunks are resampled
 * here as one continuous stream to the context rate, so there is no per-chunk
 * resampler edge (on a 44.1 kHz context the old path doubled one frame at every
 * chunk boundary: a click 25 times a second), and playout runs on the audio
 * thread from a queue with fades on underrun and flush.
 *
 * Messages in:  { type: "pcm", pcm: Int16Array, sampleRate } | { type: "flush" } | { type: "dispose" }
 * Messages out: { type: "started", frame } | { type: "active", active, underruns }
 */
import { PcmPlayoutQueue, StreamingResampler, int16ArrayToFloat } from "./voice-dsp.js"

class GravitrePcmPlayerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super()
    const opts = (options && options.processorOptions) || {}
    this.queue = new PcmPlayoutQueue({ sampleRate, ...opts })
    this.resampler = null
    this.disposed = false
    this.active = false
    this.port.onmessage = (event) => this.onMessage(event.data)
  }

  onMessage(msg) {
    if (!msg || typeof msg !== "object") return
    if (msg.type === "pcm" && msg.pcm) {
      const inRate = Number(msg.sampleRate) || 16000
      if (!this.resampler || this.resampler.inRate !== inRate) {
        this.resampler = new StreamingResampler(inRate, sampleRate)
      }
      const samples = this.resampler.process(int16ArrayToFloat(msg.pcm))
      this.queue.push(samples, currentFrame)
      this.reportActive()
    } else if (msg.type === "flush") {
      this.queue.flush()
      if (this.resampler) this.resampler.reset()
      this.reportActive()
    } else if (msg.type === "dispose") {
      this.disposed = true
    }
  }

  reportActive() {
    const active = this.queue.isActive()
    if (active === this.active) return
    this.active = active
    this.port.postMessage({ type: "active", active, underruns: this.queue.underruns })
  }

  process(_inputs, outputs) {
    if (this.disposed) return false
    const out = outputs[0] && outputs[0][0]
    if (!out) return true
    const { started } = this.queue.process(out, currentFrame, () => {
      // About to run dry: release the resampler's held-back tail first.
      if (this.resampler && this.resampler.hasPending()) {
        const tail = this.resampler.flush()
        if (tail.length) this.queue.push(tail, currentFrame)
      }
    })
    for (let c = 1; c < outputs[0].length; c++) outputs[0][c].set(out)
    if (started) this.port.postMessage({ type: "started", frame: currentFrame })
    this.reportActive()
    return true
  }
}

registerProcessor("gravitre-pcm-player", GravitrePcmPlayerProcessor)
