/**
 * Jitter buffer for streamed voice PCM.
 *
 * The server paces TTS audio to the browser at exactly real time in ~40 ms
 * chunks. Scheduling each chunk 10 ms ahead (the old behaviour) meant any
 * network or main-thread hiccup longer than 10 ms left a gap, which is the
 * choppy, breaking-up playback users heard. Instead, a reply starts with a
 * short lead so later chunks always land before the previous one ends, and the
 * lead grows after an underrun in the middle of a reply.
 */

export const PCM_JITTER_INITIAL_LEAD_S = 0.12
export const PCM_JITTER_MAX_LEAD_S = 0.32
export const PCM_JITTER_LEAD_STEP_S = 0.06
/** A chunk arriving this soon after the previous one is the same reply. */
export const PCM_SAME_REPLY_GAP_MS = 400

export type PcmJitterState = {
  leadS: number
  lastChunkAtMs: number | null
  underruns: number
}

export function createPcmJitterState(): PcmJitterState {
  return { leadS: PCM_JITTER_INITIAL_LEAD_S, lastChunkAtMs: null, underruns: 0 }
}

/**
 * Pick the AudioContext time to start the next chunk and update the state.
 *
 * Contiguous chunks play back-to-back at `nextTime`. When the queue has run
 * dry (`nextTime` is already in the past) playback restarts `leadS` ahead of
 * now; if that happened mid-reply, the lead grows for the rest of the session.
 */
export function schedulePcmStart(
  state: PcmJitterState,
  currentTime: number,
  nextTime: number,
  nowMs: number,
): number {
  const sameReply =
    state.lastChunkAtMs !== null && nowMs - state.lastChunkAtMs <= PCM_SAME_REPLY_GAP_MS
  state.lastChunkAtMs = nowMs
  if (nextTime > currentTime + 0.005) return nextTime
  if (sameReply && nextTime > 0) {
    state.underruns += 1
    state.leadS = Math.min(PCM_JITTER_MAX_LEAD_S, state.leadS + PCM_JITTER_LEAD_STEP_S)
  }
  return currentTime + state.leadS
}
