"use client"

import { useEffect, useState } from "react"
import { Mic, MicOff, Lock } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSpeechRecognition } from "@/hooks/use-speech-recognition"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"
import { getVoiceStatusDetailed } from "@/lib/tier1-voice-client"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

type VoiceInputButtonProps = {
  value: string
  onChange: (value: string) => void
  onError?: (message: string) => void
  /**
   * Optional mirror of the recognition status, so a sibling presence indicator
   * can render the real mic state instead of inferring one. Additive and
   * behaviour-free: the button works identically when this is omitted.
   */
  onStatusChange?: (status: SpeechRecognitionStatus) => void
  disabled?: boolean
  className?: string
  /** Show a visible "Dictate" label beside the mic (discoverability). */
  showLabel?: boolean
}

/**
 * Mic button for chat composers. Tap to start/stop; streams partial
 * transcription into the input field for review before send.
 * This is dictation into the composer — not the agent Voice modality toggle.
 */
export function VoiceInputButton({
  value,
  onChange,
  onError,
  onStatusChange,
  disabled = false,
  className,
  showLabel = false,
}: VoiceInputButtonProps) {
  const [orgVoiceBlocked, setOrgVoiceBlocked] = useState(false)
  const { isListening, isSupported, toggleListening, status } = useSpeechRecognition({
    value,
    disabled: disabled || orgVoiceBlocked,
    onTranscript: (text) => {
      onChange(text)
    },
    onError,
  })

  useEffect(() => {
    onStatusChange?.(status)
  }, [status, onStatusChange])

  useEffect(() => {
    let cancelled = false
    void getVoiceStatusDetailed(true).then((result) => {
      if (cancelled) return
      setOrgVoiceBlocked(Boolean(result.blocked))
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (!isSupported && !orgVoiceBlocked) return null

  if (orgVoiceBlocked) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              disabled
              aria-label="Voice dictation unavailable"
              className={cn(
                "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-border/70 bg-background/80 px-2.5 text-muted-foreground opacity-70",
                showLabel ? "min-w-[5.5rem]" : "w-9",
                className,
              )}
            >
              <Lock className="h-4 w-4" aria-hidden />
              {showLabel ? <span className="text-xs font-medium">Dictate</span> : null}
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            Voice is unavailable — turned off for this organization or not entitled for your seat.
            An admin can enable voice under Meson Addons / Billing & Plan.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  const label = isListening
    ? "Stop dictation"
    : value.trim()
      ? "Continue dictation"
      : "Dictate with voice"

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={toggleListening}
            disabled={disabled}
            aria-label={label}
            aria-pressed={isListening}
            className={cn(
              "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border transition-all",
              showLabel ? "min-w-[5.5rem] px-2.5" : "w-9",
              isListening
                ? "border-success/40 bg-success/10 text-success hover:bg-success/15"
                : "border-border/70 bg-background/80 text-muted-foreground hover:border-success/30 hover:bg-success/5 hover:text-foreground",
              disabled && "cursor-not-allowed opacity-40",
              className,
            )}
          >
            {status === "listening" ? (
              <span className="relative inline-flex">
                <Mic className="h-4 w-4" aria-hidden />
                <span
                  aria-hidden
                  className="status-live absolute -right-0.5 -top-0.5 h-1.5 w-1.5 text-success"
                />
              </span>
            ) : status === "error" || status === "permission-denied" ? (
              <MicOff className="h-4 w-4" aria-hidden />
            ) : (
              <Mic className="h-4 w-4" aria-hidden />
            )}
            {showLabel ? (
              <span className="text-xs font-medium">{isListening ? "Listening" : "Dictate"}</span>
            ) : null}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs">
          {isListening
            ? "Listening — tap to stop. Transcript fills the message box."
            : "Dictate into the message box. For speak-and-hear replies, switch Text | Voice on this chat (internal staff voice — not phone calls)."}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
