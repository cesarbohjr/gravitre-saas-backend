"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { textForSpeech } from "@/lib/speech-text"
import { synthesizeViaElevenLabs } from "@/lib/tier1-voice-client"

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
 * Tier 1 TTS: prefer ElevenLabs via `/api/voice/tts`, fall back to browser speechSynthesis.
 */
export function useSpeechSynthesis({
  text,
  messageId,
}: UseSpeechSynthesisOptions): UseSpeechSynthesisResult {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const objectUrlRef = useRef<string | null>(null)

  const isSupported =
    typeof window !== "undefined" &&
    ("speechSynthesis" in window || typeof Audio !== "undefined")

  const stop = useCallback(() => {
    const synth = getSpeechSynthesis()
    synth?.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ""
      audioRef.current = null
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
    if (activeUtteranceId === messageId) {
      activeUtteranceId = null
      activeStopHandler = null
    }
    utteranceRef.current = null
    setIsSpeaking(false)
    setIsPaused(false)
  }, [messageId])

  const speakBrowser = useCallback(
    (spokenText: string) => {
      const synth = getSpeechSynthesis()
      if (!synth) return

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
    },
    [messageId, stop],
  )

  const speak = useCallback(() => {
    const spokenText = textForSpeech(text)
    if (!spokenText) return

    if (activeUtteranceId && activeUtteranceId !== messageId) {
      activeStopHandler?.()
    }

    void (async () => {
      const paid = await synthesizeViaElevenLabs(spokenText)
      if (paid?.blob) {
        if (activeUtteranceId && activeUtteranceId !== messageId) {
          activeStopHandler?.()
        }
        const url = URL.createObjectURL(paid.blob)
        objectUrlRef.current = url
        const audio = new Audio(url)
        audioRef.current = audio
        activeUtteranceId = messageId
        activeStopHandler = stop
        setIsSpeaking(true)
        setIsPaused(false)
        audio.onended = () => stop()
        audio.onerror = () => {
          stop()
          speakBrowser(spokenText)
        }
        try {
          await audio.play()
          return
        } catch {
          stop()
        }
      }
      speakBrowser(spokenText)
    })()
  }, [messageId, speakBrowser, stop, text])

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
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current)
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
