"use client"

/**
 * Agent-chat voice playback over the same `/api/voice/tts` pipeline as main-chat
 * Read aloud. Surfaces 402/billing distinctly (no silent browser fallback).
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { textForSpeech } from "@/lib/speech-text"
import {
  synthesizeViaElevenLabsDetailed,
  type TtsSynthesizeError,
} from "@/lib/tier1-voice-client"

type SpeakOptions = {
  agentId?: string
  qaForceError?: string | null
  messageId: string
}

export type AgentVoicePlayback = {
  isSpeaking: boolean
  billingIssue: boolean
  billingDetail: string | undefined
  serviceError: boolean
  serviceDetail: string | undefined
  speak: (text: string, options: SpeakOptions) => Promise<void>
  stop: () => void
  clearBilling: () => void
  clearErrors: () => void
}

let activePlaybackId: string | null = null
let activeStop: (() => void) | null = null

export function useAgentVoicePlayback(): AgentVoicePlayback {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [billingIssue, setBillingIssue] = useState(false)
  const [billingDetail, setBillingDetail] = useState<string | undefined>()
  const [serviceError, setServiceError] = useState(false)
  const [serviceDetail, setServiceDetail] = useState<string | undefined>()
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const objectUrlRef = useRef<string | null>(null)
  const messageIdRef = useRef<string | null>(null)

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ""
      audioRef.current = null
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = null
    }
    if (activePlaybackId === messageIdRef.current) {
      activePlaybackId = null
      activeStop = null
    }
    messageIdRef.current = null
    setIsSpeaking(false)
  }, [])

  const clearBilling = useCallback(() => {
    setBillingIssue(false)
    setBillingDetail(undefined)
  }, [])

  const clearErrors = useCallback(() => {
    setBillingIssue(false)
    setBillingDetail(undefined)
    setServiceError(false)
    setServiceDetail(undefined)
  }, [])

  const applyFailure = useCallback((err: TtsSynthesizeError) => {
    if (err.billingIssue || err.errorClass === "billing" || err.status === 402) {
      setBillingIssue(true)
      setBillingDetail(err.detail || "Voice paused — credits needed")
      setServiceError(false)
      setServiceDetail(undefined)
      return
    }
    setServiceError(true)
    setServiceDetail(err.detail || "Voice unavailable right now")
    setBillingIssue(false)
    setBillingDetail(undefined)
  }, [])

  const speak = useCallback(
    async (text: string, options: SpeakOptions) => {
      const spokenText = textForSpeech(text)
      if (!spokenText) return

      if (activePlaybackId && activePlaybackId !== options.messageId) {
        activeStop?.()
      }
      stop()
      // Fresh attempt — clear prior amber until this call confirms billing again.
      clearErrors()
      messageIdRef.current = options.messageId

      const result = await synthesizeViaElevenLabsDetailed(spokenText, {
        agentId: options.agentId,
        qaForceError: options.qaForceError,
      })

      if (!result.ok) {
        // Disabled provider: no amber billing; leave presence to mic/stream.
        if (result.disabled) return
        applyFailure(result)
        return
      }

      if (activePlaybackId && activePlaybackId !== options.messageId) {
        activeStop?.()
      }
      const url = URL.createObjectURL(result.blob)
      objectUrlRef.current = url
      const audio = new Audio(url)
      audioRef.current = audio
      activePlaybackId = options.messageId
      activeStop = stop
      setIsSpeaking(true)
      audio.onended = () => stop()
      audio.onerror = () => {
        stop()
        setServiceError(true)
        setServiceDetail("Audio playback failed")
      }
      try {
        await audio.play()
      } catch {
        stop()
        setServiceError(true)
        setServiceDetail("Audio playback blocked by the browser")
      }
    },
    [applyFailure, clearErrors, stop],
  )

  useEffect(() => {
    return () => stop()
  }, [stop])

  return {
    isSpeaking,
    billingIssue,
    billingDetail,
    serviceError,
    serviceDetail,
    speak,
    stop,
    clearBilling,
    clearErrors,
  }
}
