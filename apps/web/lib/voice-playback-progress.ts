/**
 * Per-reply playback progress for the Pipecat voice socket.
 *
 * The server knows what it generated and sent; only the browser knows what was
 * played. This keeps, for each reply id, where its audio sits on the player's
 * timeline (audio is queued back to back, so reply N starts where everything
 * received before it ends) and turns the player's played seconds into
 * `playback.progress` reports:
 *
 *   { type: "playback.progress", reply_id, received_ms, played_ms,
 *     interrupted, final, reason }
 *
 * Reports go out periodically while a reply plays, when the player drains, and
 * at an interruption (server barge-in or a local one). With
 * voice_playback_grounded_history_v1 the server cuts the stored assistant
 * message to `played_ms` on an interruption.
 *
 * The browser cannot map played audio to characters (it has no word timings);
 * the server does that from the timings it saw.
 */

export const PLAYBACK_PROGRESS_INTERVAL_MS = 500
const MAX_TRACKED_REPLIES = 4

export type PlaybackProgressReason = "periodic" | "drained" | "interrupted" | "barge_in"

export type PlaybackProgressReport = {
  type: "playback.progress"
  reply_id: number
  received_ms: number
  played_ms: number
  interrupted: boolean
  final: boolean
  reason: PlaybackProgressReason
}

/**
 * `receiving`: more audio of this reply may still arrive. A newer reply's
 * audio ends it, but the reply keeps playing (and being reported) until its
 * queued audio has played out or it is interrupted; only then is it `final`.
 */
type ReplyEntry = { startS: number; receivedS: number; receiving: boolean; final: boolean }

// Played time within this of received time counts as played out (frame rounding).
const PLAYED_OUT_SLACK_S = 0.005

export type PlaybackProgressTracker = {
  /** PCM of `replyId` was queued to the player. Ignores frames with no reply id. */
  noteReceived: (replyId: unknown, samples: number, sampleRate: number) => void
  /**
   * Reports for every reply not yet finalised, given the player's played
   * seconds since its last flush. `interrupted` finalises them; `ensureReplyId`
   * reports that reply even if none of its audio arrived (played 0).
   */
  reports: (
    playedSeconds: number,
    options: { reason: PlaybackProgressReason; interrupted?: boolean; ensureReplyId?: unknown },
  ) => PlaybackProgressReport[]
  /** The player was flushed: its played count and queue restart from zero. */
  reset: () => void
  hasOpenReplies: () => boolean
}

function isReplyId(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
}

export function createPlaybackProgressTracker(): PlaybackProgressTracker {
  let entries = new Map<number, ReplyEntry>()
  let timelineS = 0

  const entryFor = (replyId: number): ReplyEntry => {
    let entry = entries.get(replyId)
    if (!entry) {
      entry = { startS: timelineS, receivedS: 0, receiving: true, final: false }
      entries.set(replyId, entry)
      if (entries.size > MAX_TRACKED_REPLIES) {
        // Drop the oldest reply whose reporting is complete; an open one only
        // when every tracked reply is still open.
        const finals = [...entries.entries()].filter(([, e]) => e.final).map(([id]) => id)
        entries.delete(Math.min(...(finals.length ? finals : [...entries.keys()])))
      }
    }
    return entry
  }

  return {
    noteReceived(replyId, samples, sampleRate) {
      if (!isReplyId(replyId) || samples <= 0) return
      const seconds = samples / (sampleRate > 0 ? sampleRate : 16000)
      if (!entries.has(replyId)) {
        // A newer reply's audio means older replies get no more audio. They
        // may still be playing, so they stay open until played out.
        for (const [otherId, other] of entries) if (otherId < replyId) other.receiving = false
      }
      const entry = entryFor(replyId)
      entry.receivedS += seconds
      timelineS += seconds
    },
    reports(playedSeconds, { reason, interrupted = false, ensureReplyId }) {
      if (isReplyId(ensureReplyId)) entryFor(ensureReplyId)
      const played = Number.isFinite(playedSeconds) ? Math.max(0, playedSeconds) : 0
      const out: PlaybackProgressReport[] = []
      for (const [replyId, entry] of [...entries.entries()].sort((a, b) => a[0] - b[0])) {
        if (entry.final) continue
        const replyPlayed = Math.min(entry.receivedS, Math.max(0, played - entry.startS))
        // Final: cut off, or no more audio coming and all of it played. This
        // report is then the reply's last, cumulative one.
        if (interrupted || (!entry.receiving && replyPlayed >= entry.receivedS - PLAYED_OUT_SLACK_S)) {
          entry.final = true
        }
        out.push({
          type: "playback.progress",
          reply_id: replyId,
          received_ms: Math.round(entry.receivedS * 1000),
          played_ms: Math.round(replyPlayed * 1000),
          interrupted,
          final: entry.final,
          reason,
        })
      }
      return out
    },
    reset() {
      // Finalised entries stay so a late duplicate interruption is not re-sent.
      const kept = new Map<number, ReplyEntry>()
      for (const [replyId, entry] of entries) if (entry.final) kept.set(replyId, entry)
      entries = kept
      timelineS = 0
    },
    hasOpenReplies() {
      for (const entry of entries.values()) if (!entry.final) return true
      return false
    },
  }
}

export function encodePlaybackProgress(report: PlaybackProgressReport): string {
  return JSON.stringify(report)
}

export type TranscriptDisposition = "final" | "backchannel" | "aside" | "interim"

/**
 * How the hook treats a `transcript` message. A final the server marked as a
 * backchannel ("yeah" over the bot, an echo of the bot, "you there?" while it
 * thinks) is not a user turn: the server dropped it, so the client must not
 * clear the reply on screen or add a user message for it.
 */
export function transcriptDisposition(msg: Record<string, unknown>): TranscriptDisposition {
  if (!msg.final) return "interim"
  if (msg.backchannel !== true) return "final"
  // "What does that mean?" while work runs: answered as an aside, and the
  // running reply stays on screen (voice_explain_aside_v1).
  return msg.turn_taking === "explain_aside" ? "aside" : "backchannel"
}

/** An assistant_text or assistant_turn.complete message that belongs to an explain aside. */
export function isAsideMessage(msg: Record<string, unknown>): boolean {
  return msg.aside === true
}

export type SpokenSegmentKind = "filler" | "progress" | "answer"

/** Label of an assistant_text delta; unlabelled (older servers) counts as answer. */
export function assistantTextKind(msg: Record<string, unknown>): SpokenSegmentKind {
  const kind = typeof msg.kind === "string" ? msg.kind : ""
  return kind === "filler" || kind === "progress" ? kind : "answer"
}

export type SpeechInterruptionKind = "speech_stop" | "interrupt"

/**
 * How the hook treats a `speech.interrupted` message. `speech_stop` ("stop
 * talking, keep working", sent behind voice_interrupt_intents_v1) silences the
 * reply's audio only: its text keeps streaming and is saved in full, so the
 * client must not reset or trim the reply on screen. Anything else is a real
 * barge-in that cuts the reply.
 */
export function speechInterruptionKind(msg: Record<string, unknown>): SpeechInterruptionKind {
  return msg.intent === "speech_stop" ? "speech_stop" : "interrupt"
}
