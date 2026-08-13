"use client"

/**
 * SHARED_CHAT_COMPOSER_CONTROLS — sole chat composer chrome for `/ai` and agent chat.
 *
 * Layout (text view):
 *   [ waveform | textarea | Browse | ↑/■ ]   ← everything inside the input pill
 *
 * There is no Text|Voice toggle and no separate Speak mic. The in-input waveform
 * is the voice control: grey/still when idle, emerald + animated when you hold
 * the floor, graphite when the agent is speaking. Clicking it toggles the mic
 * while staying in text view; when the floor is live, the speaker label opens
 * the full-page orb (voice view). Orb returns via "Tap for text view".
 *
 * Submit: green ArrowUp when ready; yellow Square (stop) while streaming,
 * listening, or TTS speaking — one button, no separate Stop row.
 */

import {
  useEffect,
  useState,
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
  GravitreVoiceWaveform,
  VoiceOrbTakeover,
  type VoiceSpeaker,
} from "@/components/gravitre/assistant/voice-presentation"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"

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
  /** @deprecated Technical upstream detail — ignored in customer UI. */
  voicePresenceDetail?: string
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
}: SharedChatComposerControlsProps) {
  const actions = trailingExtras ?? leadingExtras

  // Presentation is local: expand/collapse must not interrupt audio or lose the
  // transcript. Text view vs orb is a view preference, not session state.
  const [presentation, setPresentation] = useState<"text" | "orb">("text")

  const { isListening, isSupported, toggleListening, status } = useSpeechRecognition({
    value: input,
    disabled: disabled || !voiceEntitled,
    onTranscript: (text) => onInputChange(text),
    onError: onVoiceInputError,
  })

  useEffect(() => {
    onMicStatusChange?.(status)
  }, [status, onMicStatusChange])

  // 11a/11b speaker chrome only while Voice owns the floor (mic or TTS / voice stream).
  // Idle Text replies must not paint a graphite agent pill.
  const isLiveVoice =
    voicePresence === "listening" ||
    voicePresence === "speaking" ||
    isListening ||
    ttsSpeaking ||
    (modality === "voice" && isStreaming)
  const speaker: VoiceSpeaker =
    voicePresence === "speaking" || ttsSpeaking || (modality === "voice" && isStreaming && !isListening)
      ? "agent"
      : "user"
  const waveActive = isLiveVoice
  const speakerLabel =
    voicePresence === "listening" || isListening
      ? "You"
      : voicePresence === "speaking" || ttsSpeaking || (modality === "voice" && isStreaming)
        ? agentLabel
        : null

  const isBusy = isStreaming || ttsSpeaking || isListening

  // Orb cannot outlive a live floor — collapse when mic/TTS ends.
  useEffect(() => {
    if (!isLiveVoice && presentation === "orb") setPresentation("text")
  }, [isLiveVoice, presentation])

  const armVoice = () => {
    onModalityChange?.("voice")
  }

  const openVoiceView = () => {
    if (!voiceEntitled) return
    armVoice()
    setPresentation("orb")
  }

  const handleWaveformClick = () => {
    if (disabled || !voiceEntitled) return
    if (!isSupported) {
      onVoiceInputError?.("Voice input is not supported in this browser.")
      return
    }
    // Already listening — open immersive voice view (orb). Stop ends the mic.
    if (isListening) {
      openVoiceView()
      return
    }
    // Agent holding the floor — barge-in: stop TTS and take the mic in text view.
    if (ttsSpeaking || voicePresence === "speaking") {
      onStop?.()
      armVoice()
      toggleListening()
      return
    }
    // Idle grey waveform → arm spoken replies and start listening (stay in text view).
    armVoice()
    toggleListening()
  }

  const returnToTextView = () => setPresentation("text")

  const waveformButton = (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={handleWaveformClick}
            disabled={disabled || !voiceEntitled || (!isSupported && voiceEntitled)}
            aria-label={
              !voiceEntitled
                ? "Voice unavailable"
                : isListening
                  ? "Open voice view"
                  : "Start voice — speak your message"
            }
            aria-pressed={isListening}
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
              <GravitreVoiceWaveform
                speaker={speaker}
                active={waveActive}
                compact
              />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs">
          {!voiceEntitled
            ? unavailableReason
            : isListening
              ? "Tap again for voice view (full-page orb). Use the stop button to finish speaking."
              : "Tap to speak. Waveform turns green while you talk; graphite when the agent replies."}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )

  return (
    <div className={cn("flex flex-col gap-2", className)} data-shared-chat-composer-controls="">
      {voicePresence === "error" ? (
        <p
          className={cn("text-xs", voiceBilling ? "text-warning" : "text-muted-foreground")}
          role="status"
        >
          {voiceBilling
            ? "Voice paused — credits or payment needed"
            : "Voice unavailable right now. Try again in a moment."}
        </p>
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
          onKeyDown={onKeyDown}
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

        {speakerLabel ? (
          <button
            type="button"
            onClick={openVoiceView}
            className={cn(
              "mb-1 shrink-0 rounded-full px-2 py-1 text-xs font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#16a374]/40",
              voicePresence === "listening"
                ? "text-[#16a374] hover:bg-[#16a374]/10"
                : "text-[#3f5b52] hover:bg-muted/60 dark:text-[#e9e9e6]",
            )}
            aria-label={`Open voice view — ${speakerLabel}`}
            title="Open voice view"
          >
            {speakerLabel}
          </button>
        ) : null}

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
              onClick={onSubmit}
            >
              <ArrowUp className="h-4 w-4" />
            </Button>
          )
        ) : null}
      </div>

      {presentation === "orb" && isLiveVoice ? (
        <VoiceOrbTakeover
          speaker={speaker}
          agentLabel={agentLabel}
          onCollapse={returnToTextView}
          onExitVoice={returnToTextView}
        />
      ) : null}
    </div>
  )
}
