/**
 * Loads the voice AudioWorklet modules served from public/voice-worklets.
 *
 * Plain files under public/ (not bundled) because the AudioWorkletGlobalScope
 * fetches them by URL; voice-dsp.js is shared with the main-thread fallbacks
 * through a normal import. Bump VOICE_WORKLET_VERSION when those files change
 * so a cached copy is never paired with newer page code.
 */

export const VOICE_WORKLET_VERSION = "3"
export const VOICE_PCM_PLAYER_PROCESSOR = "gravitre-pcm-player"
export const VOICE_MIC_CAPTURE_PROCESSOR = "gravitre-mic-capture"

const MODULES = ["pcm-player-processor.js", "mic-capture-processor.js"]

const loaded = new WeakMap<BaseAudioContext, Promise<boolean>>()

export function voiceWorkletUrl(file: string): string {
  return `/voice-worklets/${file}?v=${VOICE_WORKLET_VERSION}`
}

/**
 * Resolve true once both processors are registered on `ctx`, false when this
 * browser has no AudioWorklet or loading failed (callers fall back).
 */
export function loadVoiceWorklets(ctx: BaseAudioContext): Promise<boolean> {
  const cached = loaded.get(ctx)
  if (cached) return cached
  const worklet = (ctx as BaseAudioContext & { audioWorklet?: AudioWorklet }).audioWorklet
  const pending =
    !worklet || typeof AudioWorkletNode === "undefined"
      ? Promise.resolve(false)
      : Promise.all(MODULES.map((file) => worklet.addModule(voiceWorkletUrl(file))))
          .then(() => true)
          .catch((err) => {
            if (typeof console !== "undefined") {
              console.warn("[gravitre-voice] AudioWorklet unavailable, using fallback", err)
            }
            return false
          })
  loaded.set(ctx, pending)
  return pending
}
