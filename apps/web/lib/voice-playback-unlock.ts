/**
 * Unlock browser audio output on a user gesture (mic tap / send).
 * Duplex TTS and batch Read-aloud share this so playback is not silently dropped.
 */

let sharedPlaybackContext: AudioContext | null = null

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
  return ctx
}

export function resetSharedPlaybackContextForTests(): void {
  sharedPlaybackContext = null
}
