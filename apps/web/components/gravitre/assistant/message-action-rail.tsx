"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Check, Copy, Volume2, VolumeX } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Action rail shown beneath an assistant message.
 *
 * Presentation-only interactions that need no backend:
 *  - Copy  → clipboard
 *  - Read aloud → browser SpeechSynthesis (graceful no-op if unsupported)
 *
 * Interaction model per the shipped agent-chat pattern: hover-reveal on
 * desktop, always visible on mobile, with ≥44px touch targets on small
 * screens. Icons + spacing follow Gravitre's existing design language.
 */
export function MessageActionRail({
  text,
  className,
}: {
  text: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const supportsSpeech =
    typeof window !== "undefined" && "speechSynthesis" in window

  useEffect(() => {
    return () => {
      if (copyTimer.current) clearTimeout(copyTimer.current)
      if (supportsSpeech) window.speechSynthesis.cancel()
    }
  }, [supportsSpeech])

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard can be blocked by permissions — fail quietly.
    }
  }, [text])

  const handleSpeak = useCallback(() => {
    if (!supportsSpeech) return
    const synth = window.speechSynthesis
    if (speaking) {
      synth.cancel()
      setSpeaking(false)
      return
    }
    synth.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    setSpeaking(true)
    synth.speak(utterance)
  }, [speaking, supportsSpeech, text])

  const btn =
    "inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:h-8 md:w-8"

  if (!text.trim()) return null

  return (
    <div
      className={cn(
        "mt-1 flex items-center gap-0.5 border-t border-border/40 pt-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => void handleCopy()}
        className={btn}
        aria-label={copied ? "Copied" : "Copy message"}
        title={copied ? "Copied" : "Copy"}
      >
        {copied ? (
          <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400" strokeWidth={2.5} />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>

      {supportsSpeech ? (
        <>
          <span className="mx-0.5 h-4 w-px shrink-0 bg-border/60" aria-hidden />
          <button
            type="button"
            onClick={handleSpeak}
            className={cn(btn, speaking && "text-emerald-600 dark:text-emerald-400")}
            aria-label={speaking ? "Stop reading" : "Read aloud"}
            title={speaking ? "Stop reading" : "Read aloud"}
          >
            {speaking ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
        </>
      ) : null}
    </div>
  )
}
