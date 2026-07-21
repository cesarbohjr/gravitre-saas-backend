"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { textForSpeech } from "@/lib/speech-text"

type UseSpeechSynthesisOptions = {
  text: string
  messageId: string
}

type UseSpeechSynthesisResult = {
  isSupported: boolean
  isSpeaking: boolean
  isPaused: boolean
  speak: () => void
  stop: () => void
  toggle: () => void
}

function getSpeechSynthesis(): SpeechSynthesis | null {
  if (typeof window === "undefined") return null
  return window.speechSynthesis ?? null
}

/** Active utterance id so only one message speaks at a time across the page. */
let activeUtteranceId: string | null = null
let activeStopHandler: (() => void) | null = null

/**
 * Browser-native text-to-speech for assistant messages.
 * Cleans markdown before speaking; one message at a time globally.
 */
export function useSpeechSynthesis({
  text,
  messageId,
}: UseSpeechSynthesisOptions): UseSpeechSynthesisResult {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window

  const stop = useCallback(() => {
    const synth = getSpeechSynthesis()
    synth?.cancel()
    if (activeUtteranceId === messageId) {
      activeUtteranceId = null
      activeStopHandler = null
    }
    utteranceRef.current = null
    setIsSpeaking(false)
    setIsPaused(false)
  }, [messageId])

  const speak = useCallback(() => {
    const synth = getSpeechSynthesis()
    if (!synth) return

    const spokenText = textForSpeech(text)
    if (!spokenText) return

    if (activeUtteranceId && activeUtteranceId !== messageId) {
      activeStopHandler?.()
    }

    synth.cancel()

    const utterance = new SpeechSynthesisUtterance(spokenText)
    utterance.rate = 1
    utterance.pitch = 1
    utterance.lang = "en-US"

    utterance.onstart = () => {
      activeUtteranceId = messageId
      activeStopHandler = stop
      setIsSpeaking(true)
      setIsPaused(false)
    }

    utterance.onend = () => {
      if (activeUtteranceId === messageId) {
        activeUtteranceId = null
        activeStopHandler = null
      }
      utteranceRef.current = null
      setIsSpeaking(false)
      setIsPaused(false)
    }

    utterance.onerror = () => {
      if (activeUtteranceId === messageId) {
        activeUtteranceId = null
        activeStopHandler = null
      }
      utteranceRef.current = null
      setIsSpeaking(false)
      setIsPaused(false)
    }

    utteranceRef.current = utterance
    synth.speak(utterance)
  }, [messageId, stop, text])

  const toggle = useCallback(() => {
    if (isSpeaking) {
      stop()
      return
    }
    speak()
  }, [isSpeaking, speak, stop])

  useEffect(() => {
    return () => {
      if (activeUtteranceId === messageId) {
        getSpeechSynthesis()?.cancel()
        activeUtteranceId = null
        activeStopHandler = null
      }
    }
  }, [messageId])

  return {
    isSupported,
    isSpeaking,
    isPaused,
    speak,
    stop,
    toggle,
  }
}
