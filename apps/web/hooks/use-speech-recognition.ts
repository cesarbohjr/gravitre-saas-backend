"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  getSpeechRecognitionConstructor,
  isSpeechRecognitionSupported,
  mapSpeechRecognitionError,
  speechRecognitionErrorMessage,
  type SpeechRecognitionStatus,
} from "@/lib/speech-recognition"

type UseSpeechRecognitionOptions = {
  /** Current composer value — preserved as prefix when dictation starts. */
  value?: string
  /** Called as partial and final transcripts arrive. */
  onTranscript: (text: string, meta: { isFinal: boolean }) => void
  /** Called when recognition stops or fails. */
  onError?: (message: string) => void
  lang?: string
  disabled?: boolean
}

type UseSpeechRecognitionResult = {
  status: SpeechRecognitionStatus
  isListening: boolean
  isSupported: boolean
  toggleListening: () => void
  stopListening: () => void
}

/**
 * Browser-native speech-to-text with streaming interim results.
 * Tap to start, tap again to stop — transcript streams into the caller's input field.
 */
export function useSpeechRecognition({
  value = "",
  onTranscript,
  onError,
  lang = "en-US",
  disabled = false,
}: UseSpeechRecognitionOptions): UseSpeechRecognitionResult {
  const [status, setStatus] = useState<SpeechRecognitionStatus>(() =>
    isSpeechRecognitionSupported() ? "idle" : "unsupported",
  )
  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const committedRef = useRef("")
  const prefixRef = useRef("")
  const listeningRef = useRef(false)
  const onTranscriptRef = useRef(onTranscript)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onTranscriptRef.current = onTranscript
  }, [onTranscript])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  const stopListening = useCallback(() => {
    listeningRef.current = false
    recognitionRef.current?.stop()
    setStatus((prev) => (prev === "unsupported" ? prev : "idle"))
  }, [])

  const startListening = useCallback(() => {
    if (disabled) return

    const Ctor = getSpeechRecognitionConstructor()
    if (!Ctor) {
      setStatus("unsupported")
      onErrorRef.current?.(
        "Voice input isn't supported in this browser. Try Chrome, Edge, or Safari.",
      )
      return
    }

    committedRef.current = ""
    prefixRef.current = value.trim() ? `${value.trim()} ` : ""
    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onstart = () => {
      listeningRef.current = true
      setStatus("listening")
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ""
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const chunk = result[0]?.transcript ?? ""
        if (result.isFinal) {
          committedRef.current = `${committedRef.current}${chunk}`.trim()
          if (committedRef.current) {
            committedRef.current += " "
          }
        } else {
          interim += chunk
        }
      }

      const combined = `${prefixRef.current}${committedRef.current}${interim}`.trim()
      onTranscriptRef.current(combined, { isFinal: interim.length === 0 })
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const code = mapSpeechRecognitionError(event.error)
      if (code === "aborted") return

      const message = speechRecognitionErrorMessage(code)
      if (message) {
        onErrorRef.current?.(message)
      }

      if (code === "not-allowed" || code === "service-not-allowed") {
        setStatus("permission-denied")
      } else if (code === "no-speech") {
        setStatus("no-speech")
      } else if (code === "audio-capture") {
        setStatus("audio-capture")
      } else if (code === "network") {
        setStatus("network")
      } else {
        setStatus("error")
      }
      listeningRef.current = false
    }

    recognition.onend = () => {
      listeningRef.current = false
      setStatus((prev) => {
        if (prev === "unsupported" || prev === "permission-denied") return prev
        return "idle"
      })
      recognitionRef.current = null
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      onErrorRef.current?.("Voice input is already active.")
    }
  }, [disabled, lang, value])

  const toggleListening = useCallback(() => {
    if (listeningRef.current) {
      stopListening()
      return
    }
    startListening()
  }, [startListening, stopListening])

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
      listeningRef.current = false
    }
  }, [])

  return {
    status,
    isListening: status === "listening",
    isSupported: status !== "unsupported",
    toggleListening,
    stopListening,
  }
}
