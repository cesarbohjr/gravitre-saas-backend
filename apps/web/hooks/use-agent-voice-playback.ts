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
import { unlockVoicePlayback } from "@/lib/voice-playback-unlock"

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
  /**
   * Browser autoplay gate tripped on this synthesized reply. Same failure
   * class as the full-duplex orb (see use-voice-duplex-session.ts): a
   * slow/cold TTS round-trip can outlive the click's user-activation window.
   * The audio element + blob are kept alive (not destroyed) until a fresh
   * gesture calls resumeBlockedPlayback() — previously `stop()` ran in the
   * catch and revoked the object URL, permanently losing the reply with no
   * way to hear it short of re-sending the message.
   */
  playbackBlocked: boolean
  resumeBlockedPlayback: () => Promise<void>
}

let activePlaybackId: string | null = null
let activeStop: (() => void) | null = null

export function useAgentVoicePlayback(): AgentVoicePlayback {
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [billingIssue, setBillingIssue] = useState(false)
  const [billingDetail, setBillingDetail] = useState<string | undefined>()
  const [serviceError, setServiceError] = useState(false)
  const [serviceDetail, setServiceDetail] = useState<string | undefined>()
  const [playbackBlocked, setPlaybackBlocked] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const objectUrlRef = useRef<string | null>(null)
  const messageIdRef = useRef<string | null>(null)
  const playbackBlockedRef = useRef(false)
  const webAudioSourceRef = useRef<AudioBufferSourceNode | null>(null)

  const stop = useCallback(() => {
    playbackBlockedRef.current = false
    setPlaybackBlocked(false)
    if (webAudioSourceRef.current) {
      try {
        webAudioSourceRef.current.onended = null
        webAudioSourceRef.current.stop()
      } catch {
        // Source may already have ended.
      }
      try {
        webAudioSourceRef.current.disconnect()
      } catch {
        // Best-effort teardown.
      }
      webAudioSourceRef.current = null
    }
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
      // parseTtsErrorBody already returns customer-safe copy — never surface JSON blobs.
      setBillingDetail(err.detail || "Voice paused — credits or payment needed")
      setServiceError(false)
      setServiceDetail(undefined)
      return
    }
    setServiceError(true)
    setServiceDetail(err.detail || "Voice unavailable right now. Try again in a moment.")
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
      // Prefer the already user-unlocked WebAudio context for synthesized
      // recovery speech. HTMLMediaElement autoplay policy is separate from
      // AudioContext policy, so a slow TTS round-trip could previously finish
      // with a valid blob and still fail audio.play() after user activation
      // expired. Decoding the same blob into the shared output context keeps
      // recovery on the physical path unlocked by the Talk gesture.
      const outputCtx = await unlockVoicePlayback()
      if (outputCtx?.state === "running") {
        try {
          const encoded = await result.blob.arrayBuffer()
          const buffer = await outputCtx.decodeAudioData(encoded.slice(0))
          const source = outputCtx.createBufferSource()
          source.buffer = buffer
          source.connect(outputCtx.destination)
          webAudioSourceRef.current = source
          activePlaybackId = options.messageId
          activeStop = stop
          setIsSpeaking(true)
          source.onended = () => {
            if (webAudioSourceRef.current === source) {
              webAudioSourceRef.current = null
            }
            stop()
          }
          source.start(0)
          return
        } catch {
          // Some browsers/codecs may reject decodeAudioData for the returned
          // container. Fall through to the retained HTMLAudio recovery path.
          if (webAudioSourceRef.current) {
            try {
              webAudioSourceRef.current.disconnect()
            } catch {
              // Best-effort cleanup before HTMLAudio fallback.
            }
            webAudioSourceRef.current = null
          }
        }
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
      } catch (err) {
        const blocked =
          err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "AbortError")
        if (blocked) {
          // Keep the audio element + blob alive — a fresh gesture via
          // resumeBlockedPlayback() retries the SAME reply instead of the
          // reply being silently gone with only a re-send able to hear it.
          setIsSpeaking(false)
          playbackBlockedRef.current = true
          setPlaybackBlocked(true)
          setServiceError(true)
          setServiceDetail("Audio playback is blocked. Tap Enable sound, then try again.")
          return
        }
        stop()
        setServiceError(true)
        setServiceDetail("Audio playback failed. Tap Enable sound, then try again.")
      }
    },
    [applyFailure, clearErrors, stop],
  )

  /** Fresh user gesture — retry the held reply instead of re-synthesizing it. */
  const resumeBlockedPlayback = useCallback(async () => {
    if (!playbackBlockedRef.current) return
    const audio = audioRef.current
    if (!audio) {
      playbackBlockedRef.current = false
      setPlaybackBlocked(false)
      return
    }
    await unlockVoicePlayback()
    try {
      await audio.play()
      playbackBlockedRef.current = false
      setPlaybackBlocked(false)
      setIsSpeaking(true)
      setServiceError(false)
      setServiceDetail(undefined)
    } catch {
      // Still blocked (or the element decayed) — leave state as-is so the
      // "Enable sound" affordance stays visible for another attempt.
    }
  }, [])

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
    playbackBlocked,
    resumeBlockedPlayback,
  }
}
