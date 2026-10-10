/**
 * Overlap ducking (server flag voice_overlap_duck_v1).
 *
 * While the person talks over a reply, the server holds the decision until it
 * has words (backchannel, own-voice echo, or a real interruption). Instead of
 * playing the reply at full level for that whole wait, it sends `speech.duck`
 * and the player lowers its output gain; `speech.unduck` restores it when the
 * overlap was not an interruption. A real interruption still arrives as
 * `speech.interrupted`, which flushes the reply and resets the gain, and audio
 * of a newer reply resets it too, so a reply never starts ducked.
 */

/** Output gain while ducked. */
export const VOICE_DUCK_GAIN = 0.15
/** Ramp down to the ducked gain (s). */
export const VOICE_DUCK_RAMP_S = 0.06
/** Ramp back up to full gain (s). */
export const VOICE_UNDUCK_RAMP_S = 0.12

/** Minimal AudioParam surface the ramp uses (GainNode.gain). */
export type DuckGainParam = Pick<
  AudioParam,
  "value" | "cancelScheduledValues" | "setValueAtTime" | "linearRampToValueAtTime"
>

/** Ramp `param` to the ducked or full gain from `now`, from wherever it is. */
export function rampDuckGain(param: DuckGainParam, now: number, ducked: boolean): void {
  const target = ducked ? VOICE_DUCK_GAIN : 1
  const ramp = ducked ? VOICE_DUCK_RAMP_S : VOICE_UNDUCK_RAMP_S
  try {
    param.cancelScheduledValues(now)
    param.setValueAtTime(param.value, now)
    param.linearRampToValueAtTime(target, now + ramp)
  } catch {
    try {
      param.value = target
    } catch {
      /* ignore */
    }
  }
}

/** Set `param` to full gain at `at` (after a flush fade), dropping any ramp. */
export function resetDuckGainAt(param: DuckGainParam, now: number, at: number): void {
  try {
    param.cancelScheduledValues(now)
    param.setValueAtTime(param.value, now)
    param.setValueAtTime(1, Math.max(now, at))
  } catch {
    try {
      param.value = 1
    } catch {
      /* ignore */
    }
  }
}

export type OverlapDuckState = {
  /** `speech.duck`: true when the player should duck now. */
  duck: (replyId: unknown) => boolean
  /** `speech.unduck`: true when the player should restore now. */
  unduck: (replyId: unknown) => boolean
  /** Audio frame of `replyId` arrived: true when a newer reply ends the duck. */
  audio: (replyId: unknown) => boolean
  /** `speech.interrupted` / flush / new session: true when it was ducked. */
  reset: () => boolean
  isDucked: () => boolean
}

/**
 * Which reply is ducked. A duck for a reply older than the newest audio heard
 * is stale (that reply is over) and is ignored; an unduck for another reply
 * than the ducked one still restores, since full gain is the safe state.
 */
export function createOverlapDuckState(): OverlapDuckState {
  let ducked = false
  let duckedReply: number | null = null
  let newestAudioReply: number | null = null
  return {
    duck(replyId) {
      const rid = typeof replyId === "number" ? replyId : null
      if (rid !== null && newestAudioReply !== null && rid < newestAudioReply) return false
      duckedReply = rid
      if (ducked) return false
      ducked = true
      return true
    },
    unduck() {
      if (!ducked) return false
      ducked = false
      duckedReply = null
      return true
    },
    audio(replyId) {
      if (typeof replyId !== "number") return false
      newestAudioReply = newestAudioReply === null ? replyId : Math.max(newestAudioReply, replyId)
      if (!ducked || duckedReply === null || replyId <= duckedReply) return false
      ducked = false
      duckedReply = null
      return true
    },
    reset() {
      const was = ducked
      ducked = false
      duckedReply = null
      return was
    },
    isDucked: () => ducked,
  }
}
