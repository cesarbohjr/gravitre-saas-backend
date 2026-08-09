"use client"

/**
 * SHARED_CHAT_COMPOSER_CONTROLS — sole Text|Voice control row.
 * Main `/ai` and agent chat must import this; do not duplicate markup.
 * Speak mic mounts only in Voice modality (no separate speech-to-text-only control).
 */

import type { ReactNode } from "react"
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
  className,
  leadingExtras,
}: SharedChatComposerControlsProps) {
  const showVoiceMic = modality === "voice" && voiceEntitled

  return (
    <div className={cn("flex flex-col gap-1.5", className)} data-shared-chat-composer-controls="">
      {showVoiceMic ? (
        <VoiceSessionPresence
          state={voicePresence}
          billing={voiceBilling}
          detail={voicePresenceDetail}
          className="mb-1"
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
