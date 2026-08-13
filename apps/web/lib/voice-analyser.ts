/**
 * Real AnalyserNode amplitude → 7-bin levels for GravitreVoiceWaveform.
 * Closes the keyframed-only gap from the original voice presentation work.
 */

export type VoiceAnalyserHandle = {
  /** 7 normalized levels in [0, 1]. */
  getLevels: () => number[]
  /** Peak amplitude in [0, 1]. */
  getAmplitude: () => number
  connectStream: (stream: MediaStream) => void
  connectElement: (el: HTMLAudioElement | HTMLMediaElement) => void
  disconnect: () => void
}

const BIN_COUNT = 7

export function createVoiceAnalyser(): VoiceAnalyserHandle {
  let ctx: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let source: MediaStreamAudioSourceNode | MediaElementAudioSourceNode | null = null
  let data: Uint8Array | null = null

  const ensure = () => {
    if (typeof window === "undefined") return null
    if (!ctx) {
      const AC =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AC) return null
      ctx = new AC()
    }
    if (!analyser && ctx) {
      analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.72
      data = new Uint8Array(analyser.frequencyBinCount)
    }
    return ctx
  }

  const disconnectSource = () => {
    try {
      source?.disconnect()
    } catch {
      /* ignore */
    }
    source = null
  }

  return {
    getLevels: () => {
      if (!analyser || !data) return Array.from({ length: BIN_COUNT }, () => 0)
      analyser.getByteFrequencyData(data)
      const step = Math.max(1, Math.floor(data.length / BIN_COUNT))
      const levels: number[] = []
      for (let i = 0; i < BIN_COUNT; i++) {
        let sum = 0
        for (let j = 0; j < step; j++) sum += data[i * step + j] || 0
        levels.push(Math.min(1, sum / step / 255))
      }
      return levels
    },
    getAmplitude: () => {
      if (!analyser || !data) return 0
      analyser.getByteTimeDomainData(data)
      let peak = 0
      for (let i = 0; i < data.length; i++) {
        const v = Math.abs((data[i] || 128) - 128) / 128
        if (v > peak) peak = v
      }
      return Math.min(1, peak * 1.8)
    },
    connectStream: (stream: MediaStream) => {
      const audioCtx = ensure()
      if (!audioCtx || !analyser) return
      disconnectSource()
      void audioCtx.resume().catch(() => undefined)
      source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)
    },
    connectElement: (el: HTMLAudioElement | HTMLMediaElement) => {
      const audioCtx = ensure()
      if (!audioCtx || !analyser) return
      disconnectSource()
      void audioCtx.resume().catch(() => undefined)
      source = audioCtx.createMediaElementSource(el)
      source.connect(analyser)
      analyser.connect(audioCtx.destination)
    },
    disconnect: () => {
      disconnectSource()
      if (analyser) {
        try {
          analyser.disconnect()
        } catch {
          /* ignore */
        }
      }
      if (ctx) {
        void ctx.close().catch(() => undefined)
      }
      ctx = null
      analyser = null
      data = null
    },
  }
}
