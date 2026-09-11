/**
 * What the orb is depicting, derived from real audio and real session state.
 *
 * The session already tracks `VoicePresenceState` (idle / listening /
 * understanding / thinking / speaking / interrupted / disconnected / error), and
 * that stays the source of truth for the session. But it has no notion of *the
 * user is talking right now*: while someone speaks, presence sits on "listening"
 * until the STT provider emits a boundary event. An orb that cannot distinguish
 * "waiting for you" from "hearing you" is not audio-reactive, whatever it
 * animates.
 *
 * So USER_SPEAKING is derived here from measured microphone energy, with
 * hysteresis, and AGENT_SPEAKING from measured playback energy. Everything else
 * maps from presence, because those states are genuinely about the session rather
 * than about sound.
 *
 * This module is pure on purpose. It runs at frame rate, and the decision has to
 * be provable without a microphone.
 */

import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"

export type VoiceOrbState =
  | "idle"
  | "listening"
  | "user_speaking"
  | "thinking"
  | "agent_speaking"
  | "interrupted"
  | "error"

/**
 * Onset above, release below. A single threshold makes the orb chatter on and off
 * across it several times a second on ordinary speech, because speech energy dips
 * between syllables. The gap is what makes it read as "hearing you" instead of
 * flickering.
 *
 * Values are deliberately close to the ones the existing mic speech gate uses
 * (`speechOnsetRms` 0.012 / `speechReleaseRms` 0.008 in voice-mic-capture.ts),
 * scaled for the analyser's peak-with-1.8x-boost signal rather than raw RMS.
 */
export const USER_SPEAKING_ONSET = 0.18
export const USER_SPEAKING_RELEASE = 0.1

/**
 * How long energy must stay below the release threshold before we call it
 * silence. Without this, a pause for breath reads as "stopped talking".
 */
export const USER_SPEAKING_HANG_MS = 320

export type OrbStateInput = {
  presence: VoicePresenceState
  /** Smoothed, normalized microphone energy 0-1, or null when unmeasured. */
  micLevel: number | null
  /** Smoothed, normalized agent playback energy 0-1, or null when unmeasured. */
  agentLevel: number | null
  micMuted: boolean
  sessionLive: boolean
  /** Previous decision, for hysteresis. */
  previous: VoiceOrbState
  /** ms since the level last exceeded the release threshold. */
  quietForMs: number
}

/**
 * Presence states that outrank anything the microphone is doing.
 *
 * Ordering matters and is the whole reason this is a function rather than a
 * lookup: energy on the mic while the agent talks is barge-in, not the user
 * taking the floor, and an error must never be painted over by a loud room.
 */
function presenceOverride(presence: VoicePresenceState): VoiceOrbState | null {
  switch (presence) {
    case "error":
      return "error"
    case "disconnected":
      // Not "error": the session intends to be live and is retrying. Painting a
      // hard error for a sub-second reconnect blip is its own bug.
      return "interrupted"
    case "interrupted":
      return "interrupted"
    case "thinking":
    case "understanding":
      return "thinking"
    default:
      return null
  }
}

export function resolveOrbState(input: OrbStateInput): VoiceOrbState {
  const override = presenceOverride(input.presence)
  if (override) return override

  if (!input.sessionLive) return "idle"

  // Agent playback wins over mic energy: while the agent speaks, what the mic
  // hears is mostly the agent through the speakers.
  if (input.presence === "speaking") return "agent_speaking"
  if (input.agentLevel != null && input.agentLevel >= USER_SPEAKING_ONSET) return "agent_speaking"

  // A muted mic cannot be speaking, however loud the room is.
  if (input.micMuted) return "listening"
  if (input.micLevel == null) return input.presence === "idle" ? "idle" : "listening"

  const wasSpeaking = input.previous === "user_speaking"
  if (wasSpeaking) {
    // Stay latched until energy has been below release for the hang time.
    if (input.micLevel >= USER_SPEAKING_RELEASE) return "user_speaking"
    return input.quietForMs >= USER_SPEAKING_HANG_MS ? "listening" : "user_speaking"
  }

  return input.micLevel >= USER_SPEAKING_ONSET ? "user_speaking" : "listening"
}

/** Which voice the orb is depicting, for colour. */
export function orbStateSpeaker(state: VoiceOrbState): "user" | "agent" {
  return state === "user_speaking" ? "user" : "agent"
}

/**
 * Whether the state is driven by live sound. Used to decide between the
 * amplitude-driven presentation and the idle keyframe one, and reported in the
 * DOM as `data-voice-orb-reactive`.
 */
export function orbStateIsAudioDriven(state: VoiceOrbState): boolean {
  return state === "user_speaking" || state === "agent_speaking" || state === "listening"
}

/**
 * Text for assistive technology, because none of these states may be conveyed by
 * colour or motion alone.
 */
export const ORB_STATE_LABELS: Record<VoiceOrbState, string> = {
  idle: "Voice idle",
  listening: "Listening",
  user_speaking: "Hearing you",
  thinking: "Thinking",
  agent_speaking: "Speaking",
  interrupted: "Interrupted",
  error: "Voice error",
}

// ---------------------------------------------------------------------------
// Signal conditioning
// ---------------------------------------------------------------------------

/**
 * Exponential moving average. The raw analyser peak twitches frame to frame, so
 * animating it directly looks like noise rather than breath.
 *
 * Asymmetric on purpose: attack is much faster than release. Speech onsets are
 * sharp and a slow attack makes the orb feel laggy, while a slow release is what
 * makes it settle rather than stutter between syllables.
 */
export const AMPLITUDE_ATTACK = 0.45
export const AMPLITUDE_RELEASE = 0.12

export function smoothAmplitude(previous: number, next: number): number {
  const target = Number.isFinite(next) ? Math.min(1, Math.max(0, next)) : 0
  const factor = target > previous ? AMPLITUDE_ATTACK : AMPLITUDE_RELEASE
  return previous + (target - previous) * factor
}

/** Floor for the adaptive peak, so a silent room does not amplify its own noise. */
export const NORMALIZE_MIN_PEAK = 0.12
/** How fast the observed peak decays, letting the gain recover after a shout. */
export const NORMALIZE_PEAK_DECAY = 0.995

export type AmplitudeNormalizer = { peak: number }

export function createAmplitudeNormalizer(): AmplitudeNormalizer {
  return { peak: NORMALIZE_MIN_PEAK }
}

/**
 * Scale against a decaying observed peak, so a quiet microphone still produces
 * visible motion and a loud one does not sit pinned at maximum.
 *
 * Mutates the normalizer rather than returning a new one: this runs every frame,
 * and allocating per frame is what the surrounding work is trying to avoid.
 */
export function normalizeAmplitude(normalizer: AmplitudeNormalizer, raw: number): number {
  const value = Number.isFinite(raw) ? Math.max(0, raw) : 0
  normalizer.peak = Math.max(NORMALIZE_MIN_PEAK, normalizer.peak * NORMALIZE_PEAK_DECAY, value)
  return Math.min(1, value / normalizer.peak)
}
