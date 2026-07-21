"use client"

import { Mic, MicOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSpeechRecognition } from "@/hooks/use-speech-recognition"

type VoiceInputButtonProps = {
  value: string
  onChange: (value: string) => void
  onError?: (message: string) => void
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
        isListening
          ? "border-red-500/40 bg-red-500/10 text-red-600 hover:bg-red-500/15 dark:text-red-400"
          : "border-border/70 bg-background/80 text-muted-foreground hover:border-emerald-500/30 hover:bg-emerald-500/5 hover:text-foreground",
        disabled && "cursor-not-allowed opacity-40",
        className,
      )}
    >
      {status === "listening" ? (
        <span className="relative inline-flex">
          <Mic className="h-4 w-4" aria-hidden />
          <span className="absolute -right-1 -top-1 flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
          </span>
        </span>
      ) : status === "error" || status === "permission-denied" ? (
        <MicOff className="h-4 w-4" aria-hidden />
      ) : (
        <Mic className="h-4 w-4" aria-hidden />
      )}
    </button>
  )
}
