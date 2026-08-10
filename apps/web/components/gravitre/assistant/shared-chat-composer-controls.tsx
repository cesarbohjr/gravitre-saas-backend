"use client"

/**
 * SHARED_CHAT_COMPOSER_CONTROLS — sole Text|Voice control row.
 * Main `/ai` and agent chat must import this; do not duplicate markup.
 * Speak mic mounts only in Voice modality (no separate speech-to-text-only control).
 */

import { useEffect, useState, type ReactNode } from "react"
import { ArrowUp, Square } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { VoiceInputButton } from "@/components/gravitre/assistant/voice-input-button"
import {
  VoiceModeToggle,
  type ChatModality,
} from "@/components/gravitre/assistant/voice-mode-toggle"
import {
  VoiceSessionPresence,
  type VoicePresenceState,
} from "@/components/gravitre/assistant/voice-session-presence"
import {
  VoiceOrbTakeover,
  type VoiceSpeaker,
} from "@/components/gravitre/assistant/voice-presentation"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"

export type SharedChatComposerControlsProps = {
  modality: ChatModality
  onModalityChange: (next: ChatModality) => void
  voiceEntitled: boolean
  unavailableReason?: string
  input: string
  onInputChange: (value: string) => void
  disabled?: boolean
  isStreaming?: boolean
  ttsSpeaking?: boolean
  onStop?: () => void
  onSubmit?: () => void
  canSubmit?: boolean
  showSubmit?: boolean
  micStatus?: SpeechRecognitionStatus
  onMicStatusChange?: (status: SpeechRecognitionStatus) => void
  voicePresence?: VoicePresenceState
  voiceBilling?: boolean
  voicePresenceDetail?: string
  onVoiceInputError?: (message: string) => void
  /**
   * Display name for the speaking agent, used by the orb's "… is speaking" label.
   * Department chat passes the real agent name; main chat falls back to Gravitre.
   */
  agentLabel?: string
  className?: string
  /** Extra controls between Voice toggle and Speak mic (e.g. Browse files). */
  leadingExtras?: ReactNode
}

export function SharedChatComposerControls({
  modality,
  onModalityChange,
  voiceEntitled,
  unavailableReason,
  input,
  onInputChange,
  disabled = false,
  isStreaming = false,
  ttsSpeaking = false,
  onStop,
  onSubmit,
  canSubmit = false,
  showSubmit = true,
  onMicStatusChange,
  voicePresence = "idle",
  voiceBilling = false,
  voicePresenceDetail,
  onVoiceInputError,
  agentLabel = "Gravitre",
  className,
  leadingExtras,
}: SharedChatComposerControlsProps) {
  const showVoiceMic = modality === "voice" && voiceEntitled

  // Presentation is local to the composer and intentionally NOT lifted to the
  // page: it is a view preference, and keeping it out of session state is what
  // makes "expand/collapse cannot interrupt audio or lose the transcript" true by
  // construction rather than by careful handler discipline.
  const [presentation, setPresentation] = useState<"waveform" | "orb">("waveform")

  // Who holds the floor, from the presence state the surfaces already track.
  // `listening` means the mic is open (the user); `speaking` means TTS is playing
  // (the agent). Reused rather than re-detected, per the handoff.
  const isLiveVoice = voicePresence === "listening" || voicePresence === "speaking"
  const speaker: VoiceSpeaker = voicePresence === "speaking" ? "agent" : "user"

  // A live session is a precondition for the orb, so when the floor is released
  // (agent finishes, mic closes, a 402 lands) the orb must come down on its own.
  // Without this the operator would be stranded on a full-screen overlay pulsing
  // for a session that already ended, with the composer unreachable behind it.
  useEffect(() => {
    if (!isLiveVoice && presentation === "orb") setPresentation("waveform")
  }, [isLiveVoice, presentation])

  // Same reasoning for leaving voice mode by any other route (the Text|Voice
  // toggle, an entitlement change): presentation must not survive it.
  useEffect(() => {
    if (!showVoiceMic && presentation === "orb") setPresentation("waveform")
  }, [showVoiceMic, presentation])

  return (
    <div className={cn("flex flex-col gap-1.5", className)} data-shared-chat-composer-controls="">
      {showVoiceMic ? (
        <VoiceSessionPresence
          state={voicePresence}
          billing={voiceBilling}
          detail={voicePresenceDetail}
          agentLabel={agentLabel}
          className="mb-1"
          // Expanding is only offered while someone actually holds the floor.
          // Opening a full-screen orb over an idle or errored session would show a
          // pulsing orb representing nothing, which is exactly the "animation
          // disconnected from reality" the handoff rules out.
          onExpand={isLiveVoice ? () => setPresentation("orb") : undefined}
        />
      ) : null}

      {/*
        Orb takeover. Mounted from the SHARED composer, so main chat and every
        agent chat get it from one place — a surface cannot opt out and drift.
        It renders only while a real speaker holds the floor, so the collapse on
        `!isLiveVoice` below is what guarantees the orb can never outlive the
        session it depicts.
      */}
      {showVoiceMic && presentation === "orb" && isLiveVoice ? (
        <VoiceOrbTakeover
          speaker={speaker}
          agentLabel={agentLabel}
          // Collapse returns to the waveform and stays in voice mode: it touches
          // presentation only and deliberately calls nothing on the session.
          onCollapse={() => setPresentation("waveform")}
          onExitVoice={() => {
            // Leaving voice mode is a real modality change. Reset presentation too,
            // otherwise re-entering voice would reopen straight into the orb.
            setPresentation("waveform")
            onModalityChange("text")
          }}
        />
      ) : null}
      <div className="flex shrink-0 items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <VoiceModeToggle
            mode={modality}
            onChange={onModalityChange}
            voiceEntitled={voiceEntitled}
            unavailableReason={unavailableReason}
            disabled={disabled}
          />
          {leadingExtras}
        </div>
        <div className="flex items-center gap-2">
          {showVoiceMic ? (
            <VoiceInputButton
              value={input}
              onChange={onInputChange}
              disabled={disabled}
              onStatusChange={onMicStatusChange}
              showLabel
              onError={onVoiceInputError}
              onListeningStart={() => {
                // Minimum barge-in: stop agent TTS when the user starts speaking.
                if (ttsSpeaking) onStop?.()
              }}
            />
          ) : null}
          {showSubmit ? (
            isStreaming || ttsSpeaking ? (
              <Button variant="outline" size="sm" className="h-8" type="button" onClick={onStop}>
                <Square className="mr-1 h-3 w-3" />
                Stop
              </Button>
            ) : (
              <Button
                type={onSubmit ? "button" : "submit"}
                size="icon"
                disabled={disabled || !canSubmit}
                className="h-8 w-8 rounded-full disabled:opacity-40"
                aria-label="Send message"
                onClick={onSubmit}
              >
                <ArrowUp className="h-4 w-4" />
              </Button>
            )
          ) : null}
        </div>
      </div>
    </div>
  )
}
