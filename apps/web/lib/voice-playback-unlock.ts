/**
 * Unlock browser audio output on a user gesture (mic tap / send).
 * Duplex TTS and batch Read-aloud share this so playback is not silently dropped.
 */

let sharedPlaybackContext: AudioContext | null = null
let listenersBound = false

export function getSharedPlaybackContext(): AudioContext | null {
  if (typeof window === "undefined") return null
  const AC =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!AC) return null
  if (!sharedPlaybackContext || sharedPlaybackContext.state === "closed") {
    sharedPlaybackContext = new AC()
  }
  return sharedPlaybackContext
}

/**
 * True when the context is paused but can be resumed. Safari/iOS reports
 * "interrupted" (not "suspended") once the microphone takes over the audio
 * session or a call/route change happens; checking only "suspended" left those
 * sessions stuck on "Sound is blocked" with Enable sound doing nothing.
 */
export function isResumableAudioState(state: string | undefined): boolean {
  return state !== undefined && state !== "running" && state !== "closed"
}

/**
 * Resume a paused output context. iOS can leave `resume()` pending while the
 * session is interrupted, so the wait is bounded instead of hanging the caller.
 */
export async function ensureAudioOutputRunning(
  ctx: AudioContext | null,
  timeoutMs = 1500,
): Promise<boolean> {
  if (!ctx) return false
  if (ctx.state === "running") return true
  if (!isResumableAudioState(ctx.state)) return false
  try {
    await Promise.race([
      ctx.resume(),
      new Promise((resolve) => setTimeout(resolve, timeoutMs)),
    ])
  } catch {
    /* fall through to the state check */
  }
  // Re-read through a widened type: TS narrowed `state` before the await.
  return (ctx.state as string) === "running"
}

/**
 * iOS 17+ exposes `navigator.audioSession`. Declaring play-and-record before
 * the microphone opens stops Safari from interrupting reply playback when
 * capture starts. No-op everywhere else.
 */
export function preferPlayAndRecordAudioSession(): void {
  if (typeof navigator === "undefined") return
  const session = (navigator as unknown as { audioSession?: { type?: string } }).audioSession
  if (!session) return
  try {
    session.type = "play-and-record"
  } catch {
    /* unsupported value on this browser */
  }
}

export async function unlockVoicePlayback(): Promise<AudioContext | null> {
  const ctx = getSharedPlaybackContext()
  if (!ctx) return null
  if (isResumableAudioState(ctx.state)) {
    try {
      await ctx.resume()
    } catch {
      return ctx
    }
  }
  // Prime output once so later Audio().play() calls are less likely to hit
  // autoplay gating after the initial user gesture.
  try {
    const src = ctx.createBufferSource()
    src.buffer = ctx.createBuffer(1, 1, 22050)
    src.connect(ctx.destination)
    src.start(0)
  } catch {
    /* no-op: some browsers reject this outside gestures */
  }
  return ctx
}

export function primeVoicePlaybackUnlock(): void {
  if (typeof window === "undefined" || listenersBound) return
  listenersBound = true
  const handler = () => {
    void unlockVoicePlayback()
    const ctx = getSharedPlaybackContext()
    if (!ctx || ctx.state === "running") {
      window.removeEventListener("pointerdown", handler, true)
      window.removeEventListener("keydown", handler, true)
      window.removeEventListener("touchstart", handler, true)
      listenersBound = false
    }
  }
  window.addEventListener("pointerdown", handler, true)
  window.addEventListener("keydown", handler, true)
  window.addEventListener("touchstart", handler, true)
}

export function resetSharedPlaybackContextForTests(): void {
  sharedPlaybackContext = null
  listenersBound = false
}
