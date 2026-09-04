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

export async function unlockVoicePlayback(): Promise<AudioContext | null> {
  const ctx = getSharedPlaybackContext()
  if (!ctx) return null
  if (ctx.state === "suspended") {
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
