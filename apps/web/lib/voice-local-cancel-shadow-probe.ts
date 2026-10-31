import {
  evaluateLocalCancelCandidate,
  type CancellationObservation,
  type CancellationVerdict,
} from "./voice-local-cancel-candidate"

/**
 * Transport-independent PCM frame adapter for a browser-side keyword spotter.
 *
 * The licensed KWS adapter must implement this interface; it is not bundled
 * and no recognition result is simulated. The port observes only, and never
 * sends network traffic, edits cancellation tokens, or authorizes writes.
 */
export interface KeywordSpottingEngine {
  readonly sampleRate: 16000
  readonly frameLength: number
  /** Return true only for the fully trained, distinct cancellation phrase. */
  process(frame: Int16Array): boolean | Promise<boolean>
}

export class LocalCancellationShadowProbe {
  private pending = new Int16Array(0)
  private audioStartMs: number | null = null
  private disposed = false

  constructor(
    private readonly engine: KeywordSpottingEngine,
    private readonly onObservation: (observation: CancellationObservation, verdict: CancellationVerdict) => void,
    private readonly clock: () => number = () => performance.now(),
  ) {
    if (!Number.isSafeInteger(engine.frameLength) || engine.frameLength <= 0 || engine.sampleRate !== 16000)
      throw new Error("KWS requires positive frame length and 16kHz mono PCM")
  }

  async consume(pcm: Int16Array, workActive: boolean): Promise<void> {
    if (this.disposed) throw new Error("probe disposed")
    if (!workActive) {
      this.pending = new Int16Array(0)
      this.audioStartMs = null
      return
    }
    if (!this.audioStartMs) this.audioStartMs = this.clock()
    const next = new Int16Array(this.pending.length + pcm.length)
    next.set(this.pending)
    next.set(pcm, this.pending.length)
    let offset = 0
    while (offset + this.engine.frameLength <= next.length) {
      const frame = next.slice(offset, offset + this.engine.frameLength)
      offset += this.engine.frameLength
      // Process sequentially so SDK engines never receive overlapping frames.
      if (await this.engine.process(frame)) {
        const observation: CancellationObservation = {
          audioStartMs: this.audioStartMs,
          detectedAtMs: this.clock(),
          confidence: 1, // binary engine result; NOT a calibrated probability
          phrase: "gravitre cancel task",
          source: "local_kws",
        }
        this.onObservation(observation, evaluateLocalCancelCandidate(observation, workActive))
        // Retain remainder and keep observing; never act on the result.
      }
    }
    this.pending = next.slice(offset)
  }

  dispose() {
    this.disposed = true
    this.pending = new Int16Array(0)
    this.audioStartMs = null
  }
}
