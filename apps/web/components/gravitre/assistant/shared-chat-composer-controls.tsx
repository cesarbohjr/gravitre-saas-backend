"use client"

/**
 * SHARED_CHAT_COMPOSER_CONTROLS — sole chat composer chrome for `/ai` and agent chat.
 *
 * Layout (text view):
 *   [ waveform | textarea | Browse | ↑/■ ]   ← everything inside the input pill
 *
 * Voice can run in two presentations:
 * - text view (composer + waveform)
 * - orb view (immersive voice-to-voice)
 * Both presentations are driven by the same live session state.
 *
 * Submit: green ArrowUp when ready; yellow Square (stop) while streaming,
 * listening, or TTS speaking — one button, no separate Stop row.
 */

import {
  useEffect,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react"
import { ArrowUp, Lock, Square } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { useSpeechRecognition } from "@/hooks/use-speech-recognition"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import {
  GravitreWave,
  VoiceOrbTakeover,
  type VoiceSpeaker,
} from "@/components/gravitre/assistant/voice-presentation"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import { primeVoicePlaybackUnlock, unlockVoicePlayback } from "@/lib/voice-playback-unlock"

export type SharedChatComposerControlsProps = {
  input: string
  onInputChange: (value: string) => void
  /** Fires when the user arms voice (first mic open) or explicitly returns to text-only. */
  modality?: ChatModality
  onModalityChange?: (next: ChatModality) => void
  voiceEntitled: boolean
  unavailableReason?: string
  disabled?: boolean
  isStreaming?: boolean
  ttsSpeaking?: boolean
  onStop?: () => void
  onSubmit?: () => void
  canSubmit?: boolean
  showSubmit?: boolean
  onMicStatusChange?: (status: SpeechRecognitionStatus) => void
  voicePresence?: VoicePresenceState
  voiceBilling?: boolean
  voicePresenceDetail?: string
  onClearVoiceError?: () => void
  onVoiceInputError?: (message: string) => void
  /** Display name for the speaking agent (orb + in-input pill). */
  agentLabel?: string
  className?: string
  /** Right-side extras inside the pill, before submit (e.g. Browse files icon). */
  trailingExtras?: ReactNode
  /** @deprecated Prefer trailingExtras — leading slot removed with Text|Voice toggle. */
  leadingExtras?: ReactNode
  placeholder?: string
  inputRef?: RefObject<HTMLTextAreaElement | null>
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  textareaRows?: number
  textareaClassName?: string
  /** When false, omit the outer bordered shell (parent already wraps). Default true. */
  bordered?: boolean
  /**
   * Full-duplex One Brain voice session. When provided, waveform mic control
   * drives live STT → session/turn instead of batch MediaRecorder STT.
   */
  duplex?: {
    active: boolean
    presence: VoicePresenceState
    levels?: number[] | null
    amplitude?: number | null
    toggle: () => void
    bargeIn: () => void
    supported?: boolean
    /** Browser autoplay gate tripped — reply audio held, not dropped. */
    playbackBlocked?: boolean
    /** Fresh user gesture — retries the held-back reply and unlocks future turns. */
    resumeBlockedPlayback?: () => void
  } | null
}

export function SharedChatComposerControls({
  input,
  onInputChange,
  modality = "text",
  onModalityChange,
  voiceEntitled,
  unavailableReason = "Voice is turned off for this organization, or your seat cannot use voice here. An admin can enable voice under Meson Addons / Billing.",
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
  onClearVoiceError,
  onVoiceInputError,
  agentLabel = "Gravitre",
  className,
  trailingExtras,
  leadingExtras,
  placeholder = "Ask, delegate, or search…",
  inputRef,
  onKeyDown,
  textareaRows = 1,
  textareaClassName,
  bordered = true,
  duplex = null,
}: SharedChatComposerControlsProps) {
  const actions = trailingExtras ?? leadingExtras
  const useDuplex = Boolean(duplex)

  const { isListening, isSupported, toggleListening, status } = useSpeechRecognition({
    value: input,
    disabled: disabled || !voiceEntitled || useDuplex,
    onTranscript: (text) => onInputChange(text),
    onError: onVoiceInputError,
  })

  useEffect(() => {
    if (useDuplex && duplex) {
      const mapped: SpeechRecognitionStatus =
        duplex.presence === "listening" ||
        duplex.presence === "understanding" ||
        duplex.presence === "interrupted"
          ? "listening"
          : duplex.presence === "error" || duplex.presence === "disconnected"
            ? "audio-capture"
            : "idle"
      onMicStatusChange?.(mapped)
      return
    }
    onMicStatusChange?.(status)
  }, [status, onMicStatusChange, useDuplex, duplex])

  const duplexListening =
    useDuplex &&
    duplex &&
    (duplex.active ||
      duplex.presence === "listening" ||
      duplex.presence === "understanding" ||
      duplex.presence === "thinking" ||
      duplex.presence === "speaking" ||
      duplex.presence === "interrupted")
  const effectiveListening = useDuplex ? Boolean(duplexListening) : isListening
  const effectivePresence = useDuplex && duplex ? duplex.presence : voicePresence
  const duplexSupported = duplex?.supported !== false
  const canUseVoiceInput = useDuplex ? duplexSupported : isSupported
  const showVoiceOrb = modality === "voice" && voiceEntitled

  // 11a/11b speaker chrome only while Voice owns the floor (mic or TTS / voice stream).
  // Idle Text replies must not paint a graphite agent pill.
  const isLiveVoice =
    effectivePresence === "listening" ||
    effectivePresence === "understanding" ||
    effectivePresence === "thinking" ||
    effectivePresence === "speaking" ||
    effectivePresence === "interrupted" ||
    effectiveListening ||
    ttsSpeaking ||
    (modality === "voice" && isStreaming)
  const speaker: VoiceSpeaker =
    effectivePresence === "speaking" ||
    effectivePresence === "thinking" ||
    ttsSpeaking ||
    (modality === "voice" && isStreaming && !effectiveListening)
      ? "agent"
      : "user"
  const waveActive = isLiveVoice

  const isBusy = isStreaming || ttsSpeaking || effectiveListening

  useEffect(() => {
    primeVoicePlaybackUnlock()
  }, [])

  const armVoice = () => {
    onModalityChange?.("voice")
  }

  const stopVoiceCapture = () => {
    if (useDuplex && duplex?.active) {
      duplex.toggle()
      return
    }
    if (!useDuplex && isListening) {
      toggleListening()
    }
  }

  const startVoiceCapture = () => {
    if (disabled || !voiceEntitled) return
    void unlockVoicePlayback()
    if (useDuplex && duplex) {
      if (!duplexSupported) {
        onVoiceInputError?.("Live voice is not supported in this browser.")
        return
      }
      if (
        duplex.presence === "speaking" ||
        duplex.presence === "thinking" ||
        ttsSpeaking
      ) {
        duplex.bargeIn()
        onStop?.()
        armVoice()
        if (!duplex.active) duplex.toggle()
        return
      }
      armVoice()
      if (!duplex.active) duplex.toggle()
      return
    }
    if (!isSupported) {
      onVoiceInputError?.("Voice input is not supported in this browser.")
      return
    }
    if (ttsSpeaking || voicePresence === "speaking") {
      onStop?.()
    }
    armVoice()
    if (!isListening) toggleListening()
  }

  const handleWaveformClick = () => {
    if (disabled || !voiceEntitled) return
    if (effectiveListening) {
      stopVoiceCapture()
      return
    }
    startVoiceCapture()
  }
  const exitVoiceMode = () => {
    stopVoiceCapture()
    onModalityChange?.("text")
    onClearVoiceError?.()
  }

  const waveformButton = (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={handleWaveformClick}
            disabled={disabled || !voiceEntitled}
            aria-label={
              !voiceEntitled
                ? "Voice unavailable"
                : effectiveListening
                  ? "Stop voice"
                  : "Start voice"
            }
            aria-pressed={effectiveListening}
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16a374]/40",
              voiceEntitled
                ? "hover:bg-muted/60"
                : "cursor-not-allowed opacity-50",
              disabled && "opacity-40",
            )}
          >
            {!voiceEntitled ? (
              <Lock className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
            ) : (
              <GravitreWave
                speaker={speaker}
                active={waveActive}
                compact
                levels={duplex?.levels}
              />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs">
          {!voiceEntitled
            ? unavailableReason
            : !canUseVoiceInput
              ? "Voice input is not supported in this browser."
            : effectiveListening
              ? "Tap to stop voice input."
              : "Tap to start voice input. You can always type in the box."}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )

  const voiceErrorMessage = (
    voiceBilling
      ? "Voice paused — credits or payment needed"
      : (voicePresenceDetail || "").trim() || "Voice unavailable right now. Try again in a moment."
  ).trim()
  // Prefer the hook's own flag (works even when the parent hasn't wired
  // voicePresence/voicePresenceDetail down, e.g. the pre-conversation landing
  // composer) and fall back to the message-text match for the legacy path.
  const playbackBlocked = useDuplex
    ? Boolean(duplex?.playbackBlocked)
    : /playback.+blocked/i.test(voiceErrorMessage)
  const enableSound = () => {
    void unlockVoicePlayback()
    duplex?.resumeBlockedPlayback?.()
    onClearVoiceError?.()
  }

  return (
    <div className={cn("flex flex-col gap-2", className)} data-shared-chat-composer-controls="">
      {voicePresence === "error" ? (
        <div className="flex flex-wrap items-center gap-2" role="status">
          <p className={cn("text-xs", voiceBilling ? "text-warning" : "text-muted-foreground")}>
            {voiceErrorMessage}
          </p>
          {playbackBlocked ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-6 rounded-full px-2 text-[11px]"
              onClick={enableSound}
            >
              Enable sound
            </Button>
          ) : null}
        </div>
      ) : null}

      <div
        className={cn(
          "flex min-h-[44px] items-end gap-1.5 rounded-full border bg-white px-2 py-1.5 dark:bg-[#262626]",
          bordered
            ? "border-[color:var(--chat-surface-border)] focus-within:border-[#16a374]/50"
            : "border-transparent",
        )}
      >
        {waveformButton}

        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              void unlockVoicePlayback()
            }
            onKeyDown?.(event)
          }}
          rows={textareaRows}
          disabled={disabled}
          placeholder={placeholder}
          className={cn(
            "max-h-[120px] min-h-[36px] w-full flex-1 resize-none bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-[color:var(--chat-surface-muted)] dark:text-[#f2f2f0]",
            textareaClassName,
          )}
          onInput={(event) => {
            const target = event.target as HTMLTextAreaElement
            target.style.height = "36px"
            target.style.height = `${Math.min(Math.max(target.scrollHeight, 36), 120)}px`
          }}
        />

        {actions}

        {showSubmit ? (
          isBusy ? (
            <Button
              type="button"
              size="icon"
              className="mb-0.5 h-8 w-8 shrink-0 rounded-full bg-amber-400 text-amber-950 hover:bg-amber-300"
              aria-label="Stop"
              onClick={() => {
                if (isListening) toggleListening()
                onStop?.()
              }}
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </Button>
          ) : (
            <Button
              type={onSubmit ? "button" : "submit"}
              size="icon"
              disabled={disabled || !canSubmit}
              className={cn(
                "mb-0.5 h-8 w-8 shrink-0 rounded-full",
                canSubmit && !disabled
                  ? "bg-[#16a374] text-white hover:bg-[#128a63]"
                  : "disabled:opacity-40",
              )}
              aria-label="Send message"
              onClick={() => {
                void unlockVoicePlayback()
                onSubmit?.()
              }}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )
        ) : null}
      </div>

      {showVoiceOrb ? (
        <VoiceOrbTakeover
          speaker={speaker}
          agentLabel={agentLabel}
          onExitVoice={exitVoiceMode}
          onMicToggle={handleWaveformClick}
          micActive={effectiveListening}
          amplitude={duplex?.amplitude}
          playbackBlocked={playbackBlocked}
          onEnableSound={enableSound}
        />
      ) : null}
    </div>
  )
}
