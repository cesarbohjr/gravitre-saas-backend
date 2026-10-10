/**
 * AudioWorklet playback for streamed voice PCM (Pipecat / ElevenLabs).
 *
 * Replaces one AudioBufferSourceNode per 40 ms chunk. Chunks are resampled
 * here as one continuous stream to the context rate, so there is no per-chunk
 * resampler edge (on a 44.1 kHz context the old path doubled one frame at every
 * chunk boundary: a click 25 times a second), and playout runs on the audio
 * thread from a queue with fades on underrun and flush.
 *
 * Messages in:  { type: "pcm", pcm: Int16Array, sampleRate, seq } | { type: "flush", epoch } | { type: "dispose" }
 * Messages out: { type: "started", frame } | { type: "active", active, underruns, seq }
 *               | { type: "progress", epoch, played, frame }
 *
 * `seq` echoes the last pcm message processed, so the main thread can ignore an
 * "inactive" report that was overtaken by audio it has already posted.
 *
 * `progress` counts output frames of real audio played (never the silence of
 * an underrun or a flush fade) since the flush that started `epoch`, about every
 * 50 ms while playing and once at each flush. The main thread turns it into the
 * played milliseconds it reports per reply to the server.
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
    this.seq = 0
    this.epoch = 0
    this.epochBase = 0
    this.lastProgress = 0
    this.progressFrames = Math.max(128, Math.round(0.05 * sampleRate))
    this.port.onmessage = (event) => this.onMessage(event.data)
  }

  onMessage(msg) {
    if (!msg || typeof msg !== "object") return
    if (msg.type === "pcm" && msg.pcm) {
      if (typeof msg.seq === "number") this.seq = msg.seq
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
      this.epoch = typeof msg.epoch === "number" ? msg.epoch : this.epoch + 1
      this.epochBase = this.queue.playedFrames
      this.lastProgress = 0
      this.reportProgress()
      this.reportActive()
    } else if (msg.type === "dispose") {
      this.disposed = true
    }
  }

  reportProgress() {
    const played = this.queue.playedFrames - this.epochBase
    this.lastProgress = played
    this.port.postMessage({ type: "progress", epoch: this.epoch, played, frame: currentFrame })
  }

  reportActive() {
    const active = this.queue.isActive()
    if (active === this.active) return
    this.active = active
    this.port.postMessage({ type: "active", active, underruns: this.queue.underruns, seq: this.seq })
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
    const played = this.queue.playedFrames - this.epochBase
    if (played - this.lastProgress >= this.progressFrames || (played > this.lastProgress && !this.queue.isActive())) {
      this.reportProgress()
    }
    this.reportActive()
    return true
  }
}

registerProcessor("gravitre-pcm-player", GravitrePcmPlayerProcessor)
