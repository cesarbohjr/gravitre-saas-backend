/**
 * Voice audio DSP shared by the AudioWorklet processors in this folder and the
 * main-thread fallbacks (imported from lib/voice-pcm-player.ts and
 * lib/voice-mic-capture.ts). Plain ES module with no imports, because the
 * browser loads it as-is into the AudioWorkletGlobalScope.
 */

/** Float sample in [-1, 1] to a clamped, rounded int16. Never wraps. */
export function floatToInt16(sample) {
  const s = sample > 1 ? 1 : sample < -1 ? -1 : sample || 0
  return s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff)
}

/**
 * @param {Float32Array} input
 * @param {number} [gain]
 * @returns {Int16Array}
 */
export function floatArrayToInt16(input, gain = 1) {
  const out = new Int16Array(input.length)
  for (let i = 0; i < input.length; i++) out[i] = floatToInt16(input[i] * gain)
  return out
}

/**
 * @param {Int16Array} pcm
 * @returns {Float32Array}
 */
export function int16ArrayToFloat(pcm) {
  const out = new Float32Array(pcm.length)
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 0x8000
  return out
}

const KERNEL_ZERO_CROSSINGS = 16
const KERNEL_TABLE_PHASES = 512

/**
 * Streaming band-limited resampler (Blackman-windowed sinc, any ratio).
 *
 * The old capture path picked every Nth sample with no low-pass filter, so
 * everything above 8 kHz folded back into the speech band, and it restarted its
 * read position on every 4096-frame block, which put a small phase jump at each
 * block boundary. This keeps the fractional read position and the filter
 * history across calls, so a stream split into arbitrary blocks resamples to
 * the same samples as the whole stream at once.
 */
export class StreamingResampler {
  /**
   * @param {number} inRate
   * @param {number} outRate
   */
  constructor(inRate, outRate) {
    this.inRate = inRate
    this.outRate = outRate
    this.step = inRate / outRate
    // Cutoff in cycles per input sample, a little under the lower Nyquist.
    this.cutoff = 0.5 * Math.min(1, outRate / inRate) * 0.9
    this.halfWidth = Math.ceil(KERNEL_ZERO_CROSSINGS / (2 * this.cutoff))
    const size = this.halfWidth * KERNEL_TABLE_PHASES + 2
    const table = new Float32Array(size)
    for (let i = 0; i < size; i++) {
      const x = i / KERNEL_TABLE_PHASES
      if (x >= this.halfWidth) break
      const arg = 2 * this.cutoff * x
      const sinc = arg === 0 ? 1 : Math.sin(Math.PI * arg) / (Math.PI * arg)
      const w = x / this.halfWidth
      const blackman = 0.42 + 0.5 * Math.cos(Math.PI * w) + 0.08 * Math.cos(2 * Math.PI * w)
      table[i] = sinc * blackman
    }
    this.table = table
    this.reset()
  }

  /** Forget all history: the next sample is treated as the start of a stream. */
  reset() {
    // Silence before the stream start, so output n lines up with input n*step.
    this.buf = new Float32Array(this.halfWidth * 2 + 256)
    this.len = this.halfWidth
    // Absolute input index of buf[0], and outputs produced since reset. The read
    // position is derived from these (never accumulated), so it cannot drift.
    this.bufStart = -this.halfWidth
    this.outCount = 0
  }

  /** Read position of the next output, in buffer coordinates. */
  get pos() {
    return this.outCount * this.step - this.bufStart
  }

  /** True when input is held back waiting for future samples. */
  hasPending() {
    return this.len > this.pos
  }

  /**
   * @param {Float32Array} input
   * @returns {Float32Array}
   */
  process(input) {
    if (this.inRate === this.outRate) return input.slice()
    this._append(input)
    return this._drain(this.len - this.halfWidth)
  }

  /** Emit the held-back tail (as if silence followed) and reset. */
  flush() {
    if (this.inRate === this.outRate) return new Float32Array(0)
    // Absolute index: _append may compact the buffer and move its origin.
    const endAbs = this.bufStart + this.len
    this._append(new Float32Array(this.halfWidth + 1))
    const out = this._drain(endAbs - this.bufStart)
    this.reset()
    return out
  }

  _append(input) {
    if (this.len + input.length > this.buf.length) {
      const keepFrom = Math.max(0, Math.floor(this.pos) - this.halfWidth)
      const keep = this.len - keepFrom
      const size = Math.max(this.buf.length, (keep + input.length) * 2)
      const next = new Float32Array(size)
      next.set(this.buf.subarray(keepFrom, this.len), 0)
      this.buf = next
      this.len = keep
      this.bufStart += keepFrom
    }
    this.buf.set(input, this.len)
    this.len += input.length
  }

  /** Produce every output whose position is below `limit` (buffer coordinates). */
  _drain(limit) {
    // Outputs whose absolute position n*step is below the limit; the epsilon
    // keeps an exact boundary (e.g. 44100 / 2.75625) from flipping on rounding.
    const absLimit = limit + this.bufStart
    const total = Math.max(this.outCount, Math.ceil(absLimit / this.step - 1e-9))
    const count = total - this.outCount
    const out = new Float32Array(count)
    const { buf, table, halfWidth, step, bufStart } = this
    const phases = KERNEL_TABLE_PHASES
    for (let n = 0; n < count; n++) {
      const pos = (this.outCount + n) * step - bufStart
      const centre = Math.floor(pos)
      let acc = 0
      let norm = 0
      const lo = centre - halfWidth + 1
      const hi = centre + halfWidth
      for (let k = lo; k <= hi; k++) {
        const d = Math.abs(pos - k) * phases
        const i = d | 0
        if (i >= table.length - 1) continue
        const frac = d - i
        const h = table[i] + (table[i + 1] - table[i]) * frac
        acc += buf[k] * h
        norm += h
      }
      // Normalising by the tap sum gives exact unity gain at DC for every phase.
      out[n] = norm !== 0 ? acc / norm : 0
    }
    this.outCount = total
    return out
  }
}

/**
 * Playout queue for streamed voice audio at the output sample rate. Runs
 * inside the player AudioWorklet (and in tests); pure, no Web Audio types.
 *
 * - A reply starts after a jitter lead (same policy as lib/voice-pcm-jitter.ts:
 *   120 ms, growing by 60 ms up to 320 ms after an underrun mid-reply).
 * - Underrun: the last frames before the queue runs dry are faded out, the
 *   gap is silence, and playback re-primes and fades back in. No hard edges.
 * - Flush (barge-in): a short fade-out over whatever was playing, then the
 *   queued audio is dropped. Audio pushed after the flush starts a new reply.
 */
export class PcmPlayoutQueue {
  /**
   * @param {{ sampleRate: number, initialLeadS?: number, maxLeadS?: number, leadStepS?: number, sameReplyGapS?: number, fadeS?: number, flushFadeS?: number }} options
   */
  constructor(options) {
    const rate = options.sampleRate
    this.sampleRate = rate
    this.initialLead = Math.round((options.initialLeadS ?? 0.12) * rate)
    this.maxLead = Math.round((options.maxLeadS ?? 0.32) * rate)
    this.leadStep = Math.round((options.leadStepS ?? 0.06) * rate)
    this.sameReplyGap = Math.round((options.sameReplyGapS ?? 0.4) * rate)
    this.fadeFrames = Math.max(1, Math.round((options.fadeS ?? 0.004) * rate))
    this.flushFadeFrames = Math.max(1, Math.round((options.flushFadeS ?? 0.012) * rate))
    this.lead = this.initialLead
    /** @type {Float32Array[]} */
    this.chunks = []
    this.readOffset = 0
    this.buffered = 0
    /** @type {"idle" | "priming" | "playing" | "starved"} */
    this.state = "idle"
    this.primeStart = 0
    this.lastPushFrame = -Infinity
    this.gain = 0
    /** @type {Float32Array[]} */
    this.fadingChunks = []
    this.fadingOffset = 0
    this.flushLeft = 0
    this.flushTotal = 0
    this.underruns = 0
    this.playedFrames = 0
  }

  /**
   * @param {Float32Array} samples output-rate audio
   * @param {number} nowFrame current output frame
   */
  push(samples, nowFrame) {
    if (!samples.length) return
    const sinceLast = nowFrame - this.lastPushFrame
    this.lastPushFrame = nowFrame
    this.chunks.push(samples)
    this.buffered += samples.length
    if (this.state === "idle" || this.state === "starved") {
      if (this.state === "starved" && sinceLast <= this.sameReplyGap) {
        this.underruns += 1
        this.lead = Math.min(this.maxLead, this.lead + this.leadStep)
      }
      this.state = "priming"
      this.primeStart = nowFrame
    }
  }

  flush() {
    if (this.state === "playing" || this.flushLeft > 0) {
      // Fade out what is audible now; everything queued behind it goes.
      if (this.flushLeft === 0) {
        this.fadingChunks = this.chunks
        this.fadingOffset = this.readOffset
        this.flushLeft = this.flushFadeFrames
        this.flushTotal = this.flushFadeFrames
      }
    }
    this.chunks = []
    this.readOffset = 0
    this.buffered = 0
    this.state = "idle"
    this.lead = this.initialLead
    this.lastPushFrame = -Infinity
    this.gain = 0
  }

  /** True while anything is queued, playing, or fading out. */
  isActive() {
    return this.state === "priming" || this.state === "playing" || this.flushLeft > 0
  }

  _read() {
    const chunk = this.chunks[0]
    const v = chunk[this.readOffset++]
    if (this.readOffset >= chunk.length) {
      this.chunks.shift()
      this.readOffset = 0
    }
    this.buffered -= 1
    return v
  }

  _readFading() {
    const chunk = this.fadingChunks[0]
    if (!chunk) return 0
    const v = chunk[this.fadingOffset++]
    if (this.fadingOffset >= chunk.length) {
      this.fadingChunks.shift()
      this.fadingOffset = 0
    }
    return v
  }

  /**
   * Fill `out` (one render quantum) and return what changed.
   * `beforeUnderrun` lets the caller top up the queue (e.g. a resampler tail)
   * when it is about to run dry.
   *
   * Gain follows the queue level: it can never exceed (frames left / fade
   * length), so the last frames before the queue runs dry are always a ramp
   * down to zero, and it rises back at most 1/fade per frame, so a restart
   * (new reply, or after an underrun) is always a ramp up.
   * @param {Float32Array} out
   * @param {number} nowFrame frame index of out[0]
   * @param {() => void} [beforeUnderrun]
   * @returns {{ started: boolean, underrun: boolean }}
   */
  process(out, nowFrame, beforeUnderrun) {
    const n = out.length
    let started = false
    let underrun = false
    if (this.state === "playing" && this.buffered < n && beforeUnderrun) beforeUnderrun()
    const fade = this.fadeFrames
    for (let i = 0; i < n; i++) {
      let sample = 0
      if (this.flushLeft > 0) {
        sample += this._readFading() * (this.flushLeft / (this.flushTotal + 1))
        this.flushLeft -= 1
        if (this.flushLeft === 0) {
          this.fadingChunks = []
          this.fadingOffset = 0
        }
      }
      if (this.state === "priming" && nowFrame + i - this.primeStart >= this.lead) {
        this.state = "playing"
        started = true
      }
      if (this.state === "playing") {
        if (this.buffered > 0) {
          const ceiling = this.buffered >= fade ? 1 : this.buffered / fade
          this.gain = Math.min(ceiling, this.gain + 1 / (fade + 1))
          sample += this._read() * this.gain
          this.playedFrames += 1
        } else {
          this.state = "starved"
          this.gain = 0
          underrun = true
        }
      }
      out[i] = sample
    }
    return { started, underrun }
  }
}
