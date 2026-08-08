"use client"

import { useEffect } from "react"
import { Mic, MicOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSpeechRecognition } from "@/hooks/use-speech-recognition"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"

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
}

/**
 * Mic button for chat composers. Tap to start/stop; streams partial
 * transcription into the input field for review before send.
 */
export function VoiceInputButton({
  value,
  onChange,
  onError,
  onStatusChange,
  disabled = false,
  className,
}: VoiceInputButtonProps) {
  const { isListening, isSupported, toggleListening, status } = useSpeechRecognition({
    value,
    disabled,
    onTranscript: (text) => {
      onChange(text)
    },
    onError,
  })

  useEffect(() => {
    onStatusChange?.(status)
  }, [status, onStatusChange])

  if (!isSupported) return null

  const label = isListening
    ? "Stop voice input"
    : value.trim()
      ? "Continue voice input"
      : "Start voice input"

  return (
    <button
      type="button"
      onClick={toggleListening}
      disabled={disabled}
      aria-label={label}
      aria-pressed={isListening}
      title={label}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-xl border transition-all",
        // An open mic is a live, healthy state, so it reads in the product's
        // success token rather than red — red is reserved for faults, and the
        // previous red-500 treatment made recording look like an error.
        isListening
          ? "border-success/40 bg-success/10 text-success hover:bg-success/15"
          : "border-border/70 bg-background/80 text-muted-foreground hover:border-success/30 hover:bg-success/5 hover:text-foreground",
        disabled && "cursor-not-allowed opacity-40",
        className,
      )}
    >
      {status === "listening" ? (
        // Listening reads as a filled mic plus one breathing dot. `status-live`
        // is the house halo (globals.css) and inherits currentColor, so it stays
        // in token and honours the global prefers-reduced-motion override that
        // an inline animate-ping would have escaped.
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
    </button>
  )
}
