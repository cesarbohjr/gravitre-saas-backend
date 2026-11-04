/** Content-free counters for one PCM player's lifetime; no playback decisions. */
export type PcmPlaybackDiagnostics = {
  player_kind: "worklet" | "buffer-source"
  observed_underruns: number
  /** Recovered worklet starvation, not proof of an audible defect. */
  rebuffer_events: number
  rebuffer_ms: number
  buffered_ms: number
  ducked: boolean
  duck_transitions: number
  ducked_ms: number
  flush_count: number
}

export function createPcmDiagnostics(
  kind: PcmPlaybackDiagnostics["player_kind"],
  clock: () => number,
) {
  let underruns = 0
  let bufferedMs = 0
  let rebufferEvents = 0
  let rebufferMs = 0
  let duckedSince: number | null = null
  let duckedMs = 0
  let transitions = 0
  let flushes = 0
  const setDuck = (ducked: boolean) => {
    if (ducked === (duckedSince !== null)) return
    transitions += 1
    if (ducked) duckedSince = clock()
    else if (duckedSince !== null) {
      duckedMs += Math.max(0, clock() - duckedSince) * 1000
      duckedSince = null
    }
  }
  return {
    noteQueue(count: unknown, buffered: unknown) {
      if (typeof count === "number" && Number.isFinite(count) && count >= 0) {
        underruns = Math.max(underruns, Math.floor(count))
      }
      if (typeof buffered === "number" && Number.isFinite(buffered) && buffered >= 0) {
        bufferedMs = buffered
      }
    },
    noteRebuffer(count: unknown, durationMs: unknown) {
      if (typeof count === "number" && Number.isSafeInteger(count) && count >= 0) rebufferEvents = Math.max(rebufferEvents, count)
      if (typeof durationMs === "number" && Number.isFinite(durationMs) && durationMs >= 0) rebufferMs = Math.max(rebufferMs, durationMs)
    },
    setDuck,
    flush() {
      flushes += 1
      bufferedMs = 0
      setDuck(false)
    },
    snapshot(): PcmPlaybackDiagnostics {
      return {
        player_kind: kind,
        observed_underruns: underruns,
        rebuffer_events: rebufferEvents,
        rebuffer_ms: Math.round(rebufferMs),
        buffered_ms: Math.round(bufferedMs),
        ducked: duckedSince !== null,
        duck_transitions: transitions,
        ducked_ms: Math.round(duckedMs + (duckedSince === null ? 0 : Math.max(0, clock() - duckedSince) * 1000)),
        flush_count: flushes,
      }
    },
  }
}
