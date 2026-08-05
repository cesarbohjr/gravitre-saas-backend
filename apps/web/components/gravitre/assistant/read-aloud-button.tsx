"use client"

import { useEffect, useRef } from "react"
import { Volume2, Square } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSpeechSynthesis } from "@/hooks/use-speech-synthesis"
import { textForSpeech } from "@/lib/speech-text"

type ReadAloudButtonProps = {
  messageId: string
  text: string
  className?: string
  compact?: boolean
  /**
   * Reports this message's speaking state upward so the assistant avatar can
   * show its "speaking" waveform. The hook already keeps only one utterance
   * active at a time, but it does that with a module-level variable that does not
   * trigger re-renders, so the state has to be surfaced through React.
   */
  onSpeakingChange?: (messageId: string, isSpeaking: boolean) => void
}

/**
 * Per-message read-aloud control using browser speech synthesis.
 */
export function ReadAloudButton({
  messageId,
  text,
  className,
  compact = false,
  onSpeakingChange,
}: ReadAloudButtonProps) {
  const { isSupported, isSpeaking, toggle } = useSpeechSynthesis({
    messageId,
    text,
  })

  // Kept in an effect rather than called from `toggle` because speech also ends
  // on its own (utterance `onend`/`onerror`, or another message taking over), and
  // those paths never run through this button's click handler.
  const report = useRef(onSpeakingChange)
  report.current = onSpeakingChange
  useEffect(() => {
    report.current?.(messageId, isSpeaking)
  }, [isSpeaking, messageId])

  const speakable = textForSpeech(text)
  if (!isSupported || !speakable) return null

  const label = isSpeaking ? "Stop reading aloud" : "Read response aloud"

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      aria-pressed={isSpeaking}
      title={label}
      className={cn(
        compact
          ? "flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
          : "inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/70 px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-emerald-500/30 hover:bg-emerald-500/5 hover:text-foreground",
        isSpeaking && "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        className,
      )}
    >
      {isSpeaking ? (
        <>
          <Square className="h-3 w-3 fill-current" aria-hidden />
          {!compact ? "Stop" : "Stop"}
        </>
      ) : (
        <>
          <Volume2 className="h-3 w-3" aria-hidden />
          {!compact ? "Read aloud" : "Read aloud"}
        </>
      )}
    </button>
  )
}
