/**
 * When a voice WebSocket failure should be ignored, retried, or shown to the user.
 *
 * Background, measured rather than assumed. `scripts/probe-ws-error-conditions.mjs`
 * drives a real server and shows `onerror` fires in exactly two situations:
 *
 *   close() while CONNECTING   -> error, close
 *   connection refused         -> error, close
 *
 * while close() from OPEN, an unclean server terminate, and a server close(1008)
 * all reach `onclose` only. (Caveat: browsers additionally fire `error` on an
 * unclean server teardown, where Node's `ws` does not. The policy therefore treats
 * close and error alike and keys off intent, not off which handler fired.)
 *
 * That first row is the "Voice connection interrupted" bug: `teardownMic()` calls
 * `ws.close()` unconditionally, so a deliberate hangup during the connect window
 * -- which the old mute button did on every press -- fired `onerror` and toasted
 * the user about a failure they had just asked for.
 *
 * Keeping the decision here, pure and synchronous, is what makes it exhaustively
 * testable without a DOM or a live session.
 */

export const VOICE_RECONNECT_MAX_ATTEMPTS = 3
export const VOICE_RECONNECT_BASE_DELAY_MS = 300
export const VOICE_RECONNECT_MAX_DELAY_MS = 4_000

export type SocketFailureContext = {
  /**
   * The app asked for this teardown: stop(), toggle() off, or unmount. Never
   * surface an error for it and never reconnect -- this is the root-cause guard.
   */
  intentional: boolean
  /** The user still wants a session. False once stop() has run to completion. */
  sessionActive: boolean
  /** Reconnects already attempted for this session. */
  attempt: number
  /** Socket reached OPEN at least once. A never-opened socket is a start failure. */
  everOpened: boolean
  maxAttempts?: number
  /** Injectable so tests drive the real decision path on a compressed schedule. */
  baseDelayMs?: number
  maxDelayMs?: number
}

export type ReconnectDecision =
  | { action: "ignore"; reason: "intentional" | "session-ended" }
  | { action: "reconnect"; delayMs: number; attempt: number }
  | { action: "surface-error"; reason: "retries-exhausted"; attempts: number }

/**
 * Exponential backoff, capped. Deterministic by default so the schedule can be
 * asserted; pass `jitter` to spread real retries across concurrent clients.
 */
export function reconnectDelayMs(
  attempt: number,
  opts: { baseMs?: number; maxMs?: number; jitter?: () => number } = {},
): number {
  const base = opts.baseMs ?? VOICE_RECONNECT_BASE_DELAY_MS
  const max = opts.maxMs ?? VOICE_RECONNECT_MAX_DELAY_MS
  const safeAttempt = Math.max(0, Math.floor(attempt))
  const raw = base * 2 ** safeAttempt
  const capped = Math.min(max, raw)
  if (!opts.jitter) return capped
  // Full jitter over [capped/2, capped]: keeps the cap meaningful while avoiding a
  // synchronised retry stampede when a backend restart drops every session at once.
  const half = capped / 2
  return Math.round(half + opts.jitter() * half)
}

export function decideSocketFailure(ctx: SocketFailureContext): ReconnectDecision {
  // Order matters. Intent is checked before everything else: a deliberate hangup
  // is not a failure, whatever the socket state or attempt count says.
  if (ctx.intentional) return { action: "ignore", reason: "intentional" }
  if (!ctx.sessionActive) return { action: "ignore", reason: "session-ended" }

  const maxAttempts = ctx.maxAttempts ?? VOICE_RECONNECT_MAX_ATTEMPTS
  if (ctx.attempt < maxAttempts) {
    return {
      action: "reconnect",
      delayMs: reconnectDelayMs(ctx.attempt, {
        baseMs: ctx.baseDelayMs,
        maxMs: ctx.maxDelayMs,
      }),
      attempt: ctx.attempt + 1,
    }
  }
  return { action: "surface-error", reason: "retries-exhausted", attempts: ctx.attempt }
}

/**
 * Server-sent `{type:"error"}` frames are refusals, not transport faults: bad
 * token, no seat, org disabled, pipecat off. Retrying cannot change the answer and
 * only delays telling the user, so these bypass the reconnect ladder entirely.
 */
/** Shown only when the socket died without the server telling us anything. */
export const VOICE_GENERIC_FAILURE_MESSAGE = "Voice connection interrupted"

/**
 * What to tell the user once the reconnect ladder is spent.
 *
 * Retryable server refusals (notably `service_failure` — every STT provider
 * failed to start) arrive as an error frame carrying a real explanation, and are
 * then followed by a clean close. The old code surfaced the generic string at the
 * end of the ladder, which overwrote that explanation with strictly less
 * information: the user watched an accurate message be replaced by
 * "Voice connection interrupted" three retries later.
 *
 * Prefer whatever the server actually said. Fall back to the generic text only
 * when the socket died without explaining itself, which is the one case where
 * "interrupted" is the honest description.
 */
export function resolveFailureMessage(lastServerError?: string | null): string {
  const trimmed = (lastServerError ?? "").trim()
  return trimmed || VOICE_GENERIC_FAILURE_MESSAGE
}

export function isTerminalServerErrorClass(errorClass: unknown): boolean {
  return (
    typeof errorClass === "string" &&
    ["auth", "forbidden", "not_enabled", "not_configured", "billing", "entitlement"].includes(
      errorClass,
    )
  )
}
