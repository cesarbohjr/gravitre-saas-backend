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
   * can render the real mic state instead of inferring one.
   */
  onStatusChange?: (status: SpeechRecognitionStatus) => void
  /** Fired when the user starts listening (not when stopping). Use to barge-in on TTS. */
  onListeningStart?: () => void
  disabled?: boolean
  className?: string
  /** Visible label beside the mic (Voice modality only). */
  showLabel?: boolean
}

/**
 * Mic for Voice modality: capture speech for the Text|Voice conversation path.
 * Not a separate speech-to-text-only product — only mounted when Text|Voice is Voice.
 */
export function VoiceInputButton({
  value,
  onChange,
  onError,
  onStatusChange,
  onListeningStart,
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
              className={cn(
                "inline-flex h-8 items-center gap-1.5 rounded-lg border border-border/70 px-2 text-muted-foreground opacity-60",
                className,
              )}
              aria-label="Voice input unavailable"
            >
              <Lock className="h-3.5 w-3.5" />
              {showLabel ? <span className="text-xs font-medium">Speak</span> : null}
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            Voice is turned off for this organization, or your seat cannot use voice here.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  const label = isListening
    ? "Stop listening"
    : status === "permission-denied"
      ? "Microphone blocked"
      : "Speak"

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={() => {
              if (!isListening) onListeningStart?.()
              toggleListening()
            }}
            disabled={disabled}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-lg border px-2 transition-colors",
              isListening
                ? "border-[#16a374]/50 bg-[#16a374]/10 text-[#16a374]"
                : "border-border/70 bg-background text-muted-foreground hover:text-foreground",
              disabled && "opacity-40",
              className,
            )}
            aria-label={label}
            aria-pressed={isListening}
          >
            {isListening ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
            {showLabel ? (
              <span className="text-xs font-medium">{isListening ? "Listening" : "Speak"}</span>
            ) : null}
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs">
          {isListening
            ? "Tap to finish speaking. Your words become the next Voice turn."
            : "Speak your message. Replies play aloud while Text | Voice is set to Voice."}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
