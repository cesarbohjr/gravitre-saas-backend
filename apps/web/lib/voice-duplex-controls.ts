/**
 * One place that maps a duplex voice session onto the composer's `duplex` prop.
 *
 * This existed inline, duplicated per chat surface. That duplication is why the
 * float, shell and mobile surfaces silently had no live voice at all: they render
 * the same composer, but each bridge built its own props and simply omitted
 * `duplex`, which downgrades the mic button to batch Web Speech with no visible
 * difference. Adding a field (mute, say) also meant editing every copy.
 *
 * Anything that renders the composer and wants real voice-to-voice passes the
 * result of this function.
 */
import type { SharedChatComposerControlsProps } from "@/components/gravitre/assistant/shared-chat-composer-controls"

export type DuplexControls = NonNullable<SharedChatComposerControlsProps["duplex"]>

/**
 * The voice-related props a chat surface forwards to the composer, as one object.
 *
 * Grouped deliberately: these were previously eight loose props, and the float,
 * shell and mobile bridges each omitted all of them. A single prop makes "this
 * surface has voice" one decision instead of eight chances to forget one.
 */
export type ChatSurfaceVoiceProps = Pick<
  SharedChatComposerControlsProps,
  | "duplex"
  | "modality"
  | "onModalityChange"
  | "voicePresence"
  | "voicePresenceDetail"
  | "voiceBilling"
  | "onVoiceInputError"
  | "onClearVoiceError"
  | "onMicStatusChange"
  | "agentLabel"
  | "voiceOrbVariant"
>

/** The subset of `useVoiceDuplexSession()` the composer needs. */
export type DuplexSessionLike = {
  isActive: boolean
  presence: DuplexControls["presence"]
  lastServerError?: string | null
  levels?: number[] | null
  amplitude?: number | null
  playbackBlocked?: boolean
  micMuted?: boolean
  toggle: () => void
  toggleMicMute?: () => void
  bargeIn: () => unknown
  resumeBlockedPlayback: () => unknown
}

export type DuplexControlsExtras = {
  /** Read-aloud playback gate, ORed with the duplex session's own. */
  alsoPlaybackBlocked?: boolean
  /** Additional playback to resume alongside the duplex session's. */
  alsoResumePlayback?: () => unknown
}

export function buildDuplexControls(
  session: DuplexSessionLike,
  extras: DuplexControlsExtras = {},
): DuplexControls {
  return {
    active: session.isActive,
    presence: session.presence,
    lastServerError: session.lastServerError ?? null,
    levels: session.levels,
    amplitude: session.amplitude,
    micMuted: session.micMuted,
    toggle: session.toggle,
    toggleMicMute: session.toggleMicMute,
    bargeIn: () => {
      void session.bargeIn()
    },
    // getUserMedia is absent on insecure origins and in some embedded webviews, so
    // this is a capability check rather than a browser sniff.
    supported: typeof window !== "undefined" && !!navigator.mediaDevices,
    playbackBlocked: Boolean(session.playbackBlocked) || Boolean(extras.alsoPlaybackBlocked),
    resumeBlockedPlayback: () => {
      void session.resumeBlockedPlayback()
      void extras.alsoResumePlayback?.()
    },
  }
}
