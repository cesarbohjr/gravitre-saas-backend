"use client"

/**
 * Full-duplex voice session: live Deepgram STT → turn-taking →
 * POST /api/voice/session/turn (CognitiveTurnKernel) → streaming TTS + barge-in.
 * Shares conversation_id with text chat — not a parallel brain.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { createVoiceAnalyser, type VoiceAnalyserHandle } from "@/lib/voice-analyser"
import { unlockVoicePlayback } from "@/lib/voice-playback-unlock"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import {
  cancelVoiceSessionTurn,
  mintDeepgramLiveTokenDetailed,
  postTurnTakingEvent,
  streamVoiceSessionTurn,
  type VoiceSessionEvent,
} from "@/lib/tier1-voice-client"

export type DuplexLatencyStages = {
  mic_open_to_first_partial_ms?: number
  partial_to_utterance_end_ms?: number
  endpoint_to_finalize_ms?: number
  finalize_to_session_request_ms?: number
  session_ttft_ms?: number
  session_ttfa_ms?: number
  e2e_speech_end_to_audio_start_ms?: number
  barge_in_cancel_ms?: number
  speculative_start_ms?: number
  speculative_restart_ms?: number
  speculative_saved_ms?: number
}

export type DuplexTurnResult = {
  userText: string
  assistantText: string
  conversationId: string | null
  turnId: string | null
  cancelled: boolean
  events: VoiceSessionEvent[]
  latency: DuplexLatencyStages
}

type Options = {
  enabled?: boolean
  conversationId?: string | null
  agentId?: string | null
  sensitivity?: string
  getHistory?: () => Array<{ role: string; content: string }>
  onUserFinal?: (text: string) => void
  onAssistantDelta?: (text: string) => void
  onTurnComplete?: (result: DuplexTurnResult) => void
  onError?: (message: string, billing?: boolean) => void
  onConversationId?: (id: string) => void
}

function downsampleTo16k(input: Float32Array, inputRate: number): Int16Array {
  if (inputRate === 16000) {
    const out = new Int16Array(input.length)
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i] ?? 0))
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    return out
  }
  const ratio = inputRate / 16000
  const newLen = Math.max(1, Math.floor(input.length / ratio))
  const out = new Int16Array(newLen)
  for (let i = 0; i < newLen; i++) {
    const s = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)] ?? 0))
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return out
}

function normalizeTranscript(text: string): string {
  return text.trim().toLowerCase().replace(/\s+/g, " ")
}

/** True when final meaningfully diverges from the speculative partial (restart needed). */
function speculativeTranscriptDiverged(partial: string, finalText: string): boolean {
  const a = normalizeTranscript(partial)
  const b = normalizeTranscript(finalText)
  if (!a || !b) return true
  if (a === b) return false
  // Final is a short extension of the partial — keep speculative turn.
  if (b.startsWith(a) && b.length - a.length <= 24) return false
  if (a.startsWith(b) && a.length - b.length <= 12) return false
  const wa = new Set(a.split(" ").filter(Boolean))
  const wb = new Set(b.split(" ").filter(Boolean))
  let inter = 0
  for (const w of wa) if (wb.has(w)) inter += 1
  const union = wa.size + wb.size - inter
  if (union === 0) return true
  return inter / union < 0.72
}

export function useVoiceDuplexSession(options: Options) {
  const [presence, setPresence] = useState<VoicePresenceState>("idle")
  const [levels, setLevels] = useState<number[] | null>(null)
  const [amplitude, setAmplitude] = useState<number | null>(null)
  const [provisionalTranscript, setProvisionalTranscript] = useState("")
  const [latency, setLatency] = useState<DuplexLatencyStages>({})
  const [isActive, setIsActive] = useState(false)
  // Browser autoplay gate tripped mid-session (e.g. a slow cold turn outlives the
  // "Talk" tap's user-activation window). The reply audio is kept queued rather
  // than dropped — see playNext's catch — until a fresh gesture calls
  // resumeBlockedPlayback(). Root cause of "no audio, no visible error": this used
  // to silently discard the blob and suppress its own toast with nothing else
  // surfacing it, so the orb looked normal forever with zero sound.
  const [playbackBlocked, setPlaybackBlocked] = useState(false)

  const optsRef = useRef(options)
  optsRef.current = options

  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const analyserRef = useRef<VoiceAnalyserHandle | null>(null)
  const rafRef = useRef<number | null>(null)
  const turnStateRef = useRef<Record<string, unknown> | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const turnIdRef = useRef<string | null>(null)
  const agentSpeakingRef = useRef(false)
  const audioElRef = useRef<HTMLAudioElement | null>(null)
  const playbackWiredRef = useRef(false)
  const audioQueueRef = useRef<Blob[]>([])
  const playingRef = useRef(false)
  const playbackBlockedRef = useRef(false)
  const marksRef = useRef<Record<string, number>>({})
  const activeRef = useRef(false)
  const speculativeRef = useRef<{
    text: string
    turnId: string
    startedAt: number
  } | null>(null)

  const stopPlayback = useCallback(() => {
    playingRef.current = false
    audioQueueRef.current = []
    playbackWiredRef.current = false
    playbackBlockedRef.current = false
    setPlaybackBlocked(false)
    const el = audioElRef.current
    if (el) {
      try {
        el.pause()
        el.removeAttribute("src")
        el.load()
      } catch {
        /* ignore */
      }
    }
    audioElRef.current = null
  }, [])

  const playNext = useCallback(async () => {
    if (playingRef.current) return
    // Autoplay gate is open — wait for resumeBlockedPlayback() (a fresh user
    // gesture) instead of burning through the queue on every arriving chunk,
    // each of which would fail the same way and previously got silently dropped.
    if (playbackBlockedRef.current) return
    const next = audioQueueRef.current.shift()
    if (!next) return
    playingRef.current = true

    await unlockVoicePlayback()

    if (!audioElRef.current) {
      const el = new Audio()
      el.onended = () => {
        playingRef.current = false
        void playNext()
      }
      el.onerror = () => {
        playingRef.current = false
        optsRef.current.onError?.("Audio playback failed during voice reply")
        void playNext()
      }
      audioElRef.current = el
    }
    const el = audioElRef.current
    const url = URL.createObjectURL(next)
    if (analyserRef.current && !playbackWiredRef.current) {
      try {
        analyserRef.current.connectElement(el)
        playbackWiredRef.current = true
      } catch {
        /* analyser optional — still attempt audible playback */
      }
    }
    el.src = url
    try {
      await el.play()
    } catch (err) {
      playingRef.current = false
      URL.revokeObjectURL(url)
      const blocked =
        err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "AbortError")
      if (blocked) {
        // Keep the reply — put it back at the front of the queue rather than
        // discarding it, and stop draining until a real gesture unlocks output.
        // Immediately retrying here would just fail identically on repeat, so
        // the queue would silently empty out with the user hearing nothing.
        audioQueueRef.current.unshift(next)
        playbackBlockedRef.current = true
        setPlaybackBlocked(true)
        optsRef.current.onError?.(
          "Audio playback is blocked. Tap Talk once to enable sound, then try again.",
        )
        return
      }
      optsRef.current.onError?.("Audio playback failed during voice reply")
      void playNext()
    }
  }, [])

  /** Fresh user gesture (tap "Enable sound" / mic) — retry the held-back reply. */
  const resumeBlockedPlayback = useCallback(async () => {
    if (!playbackBlockedRef.current) return
    await unlockVoicePlayback()
    playbackBlockedRef.current = false
    setPlaybackBlocked(false)
    void playNext()
  }, [playNext])

  const enqueueAudio = useCallback(
    (b64: string, contentType?: string) => {
      const raw = atob(b64)
      const bytes = new Uint8Array(raw.length)
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
      audioQueueRef.current.push(new Blob([bytes], { type: contentType || "audio/mpeg" }))
      playNext()
    },
    [playNext],
  )

  const stopRaf = () => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
  }

  const startRaf = () => {
    stopRaf()
    const tick = () => {
      const a = analyserRef.current
      if (a && activeRef.current) {
        setLevels(a.getLevels())
        setAmplitude(a.getAmplitude())
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
  }

  const teardownMic = useCallback(() => {
    stopRaf()
    try {
      processorRef.current?.disconnect()
    } catch {
      /* ignore */
    }
    processorRef.current = null
    try {
      audioCtxRef.current?.close()
    } catch {
      /* ignore */
    }
    audioCtxRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    try {
      wsRef.current?.close()
    } catch {
      /* ignore */
    }
    wsRef.current = null
    analyserRef.current?.disconnect()
    analyserRef.current = null
    setLevels(null)
    setAmplitude(null)
  }, [])

  const bargeIn = useCallback(async () => {
    const t0 = performance.now()
    setPresence("interrupted")
    agentSpeakingRef.current = false
    stopPlayback()
    abortRef.current?.abort()
    abortRef.current = null
    const tid = turnIdRef.current
    if (tid) {
      await cancelVoiceSessionTurn({
        turnId: tid,
        conversationId: optsRef.current.conversationId,
        reason: "barge_in",
      }).catch(() => false)
    }
    const ms = Math.round(performance.now() - t0)
    setLatency((prev) => ({ ...prev, barge_in_cancel_ms: ms }))
    if (activeRef.current) setPresence("listening")
  }, [stopPlayback])

  const runSessionTurn = useCallback(
    async (finalText: string, opts?: { speculative?: boolean }) => {
      const text = finalText.trim()
      if (!text) return
      // Avoid stacking a second turn while speculative reasoning is already in flight
      // for the same (or near-same) transcript.
      if (!opts?.speculative && speculativeRef.current) {
        const spec = speculativeRef.current
        if (!speculativeTranscriptDiverged(spec.text, text)) {
          const saved = Math.round(performance.now() - spec.startedAt)
          setLatency((p) => ({ ...p, speculative_saved_ms: saved }))
          speculativeRef.current = null
          return
        }
        // Final diverged — cancel speculative via existing Redis-backed cancel path.
        const restartAt = performance.now()
        abortRef.current?.abort()
        await cancelVoiceSessionTurn({
          turnId: spec.turnId,
          conversationId: optsRef.current.conversationId,
          reason: "speculative_transcript_mismatch",
        }).catch(() => false)
        stopPlayback()
        speculativeRef.current = null
        setLatency((p) => ({
          ...p,
          speculative_restart_ms: Math.round(performance.now() - restartAt),
        }))
      }
      if (!opts?.speculative) {
        optsRef.current.onUserFinal?.(text)
      }
      setPresence("thinking")
      const turnId =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `vt-${Date.now()}`
      turnIdRef.current = turnId
      if (opts?.speculative) {
        speculativeRef.current = { text, turnId, startedAt: performance.now() }
        setLatency((p) => ({
          ...p,
          speculative_start_ms: Math.round(performance.now() - (marksRef.current.first_partial || performance.now())),
        }))
      }
      const abort = new AbortController()
      abortRef.current = abort
      const tReq = performance.now()
      marksRef.current.finalize_to_session = tReq
      const utteranceEnd = marksRef.current.utterance_end
      if (utteranceEnd && !opts?.speculative) {
        setLatency((prev) => ({
          ...prev,
          endpoint_to_finalize_ms: Math.round(tReq - utteranceEnd),
          finalize_to_session_request_ms: 0,
        }))
      }

      let assistantText = ""
      let conversationId = optsRef.current.conversationId || null
      let cancelled = false
      let completionDispatched = false
      let sawTextDelta = false
      const events: VoiceSessionEvent[] = []
      const stage: DuplexLatencyStages = {}

      const dispatchTurnComplete = () => {
        if (completionDispatched) return
        completionDispatched = true
        optsRef.current.onTurnComplete?.({
          userText: text,
          assistantText: assistantText.trim(),
          conversationId,
          turnId,
          cancelled: cancelled || abort.signal.aborted,
          events: [...events],
          latency: stage,
        })
      }

      const result = await streamVoiceSessionTurn({
        text,
        conversationId,
        agentId: optsRef.current.agentId,
        history: optsRef.current.getHistory?.() || [],
        turnId,
        signal: abort.signal,
        onEvent: (event) => {
          events.push(event)
          if (typeof event.conversation_id === "string" && event.conversation_id) {
            conversationId = event.conversation_id
            optsRef.current.onConversationId?.(event.conversation_id)
          }
          if (event.type === "voice.ttft" && typeof event.ms === "number") {
            stage.session_ttft_ms = event.ms
            setLatency((p) => ({ ...p, session_ttft_ms: event.ms as number }))
          }
          if (event.type === "voice.ttfa" && typeof event.ms === "number") {
            stage.session_ttfa_ms = event.ms
            const e2e =
              utteranceEnd != null
                ? Math.round(performance.now() - utteranceEnd)
                : undefined
            stage.e2e_speech_end_to_audio_start_ms = e2e
            setLatency((p) => ({
              ...p,
              session_ttfa_ms: event.ms as number,
              e2e_speech_end_to_audio_start_ms: e2e,
            }))
          }
          if (event.type === "voice.agent_speech.start") {
            agentSpeakingRef.current = true
            setPresence("speaking")
          }
          if (event.type === "voice.audio.delta" && typeof event.audio_base64 === "string") {
            enqueueAudio(
              event.audio_base64,
              typeof event.content_type === "string" ? event.content_type : undefined,
            )
          }
          if (event.type === "voice.turn.cancelled") {
            cancelled = true
            stopPlayback()
          }
          if (event.type === "voice.turn.complete" || event.type === "voice.session.ended") {
            if (typeof event.text === "string") assistantText = event.text
            if (typeof event.transcript === "string" && !assistantText) {
              assistantText = event.transcript
            }
            if (event.cancelled) cancelled = true
          }
          if (event.type === "voice.turn.complete") {
            dispatchTurnComplete()
          }
          if (event.type === "voice.text.delta" && typeof event.delta === "string") {
            sawTextDelta = true
            assistantText += String(event.delta)
            optsRef.current.onAssistantDelta?.(assistantText)
          }
          if (event.type === "voice.audio.delta" && typeof event.text_chunk === "string") {
            if (!sawTextDelta) {
              optsRef.current.onAssistantDelta?.(String(event.text_chunk))
            }
          }
          if (event.type === "voice.error") {
            const billing = Boolean((event as { billing_issue?: boolean }).billing_issue)
            optsRef.current.onError?.(
              String((event as { detail?: string }).detail || "Voice turn failed"),
              billing,
            )
            setPresence(billing ? "error" : "error")
          }
        },
      })

      if (speculativeRef.current?.turnId === turnId) {
        speculativeRef.current = null
      }

      if (!result.ok && !abort.signal.aborted) {
        optsRef.current.onError?.(result.error || "Voice session failed")
        setPresence("error")
      }

      const completeEv = result.events.find((e) => e.type === "voice.turn.complete")
      const finalAssistant =
        assistantText ||
        (typeof completeEv?.text === "string" ? completeEv.text : "") ||
        ""
      if (!completionDispatched) {
        optsRef.current.onTurnComplete?.({
          userText: text,
          assistantText: finalAssistant,
          conversationId,
          turnId,
          cancelled: cancelled || abort.signal.aborted,
          events: result.events.length ? result.events : events,
          latency: stage,
        })
      }

      agentSpeakingRef.current = false
      turnIdRef.current = null
      abortRef.current = null
      if (activeRef.current && !cancelled) setPresence("listening")
      else if (activeRef.current) setPresence("listening")
    },
    [enqueueAudio, stopPlayback],
  )

  const handleDeepgramMessage = useCallback(
    async (raw: MessageEvent) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(String(raw.data)) as Record<string, unknown>
      } catch {
        return
      }
      const type = String(data.type || "")
      // Deepgram Results — alternatives expose transcript + confidence; some models
      // also emit stability on interim Results (used for speculative reasoning).
      const channel = data.channel as
        | {
            alternatives?: Array<{
              transcript?: string
              confidence?: number
              stability?: number
            }>
          }
        | undefined
      const alt = channel?.alternatives?.[0]
      const transcript = String(alt?.transcript || "").trim()
      const confidence = Number(alt?.confidence ?? data.confidence ?? 0)
      const stability = Number(data.stability ?? alt?.stability ?? 0)
      const isFinal = Boolean(data.is_final || data.speech_final)

      if (type === "SpeechStarted" || type === "speech_started") {
        // Acoustic barge-in while agent holds the floor
        if (agentSpeakingRef.current) {
          await bargeIn()
        }
        marksRef.current.speech_started = performance.now()
        setPresence("listening")
      }

      // Some providers/browsers occasionally miss an explicit SpeechStarted frame.
      // Treat first real transcript while agent audio is active as immediate barge-in.
      if (transcript && agentSpeakingRef.current) {
        await bargeIn()
      }

      if (transcript) {
        if (!marksRef.current.first_partial) {
          marksRef.current.first_partial = performance.now()
          const micOpen = marksRef.current.mic_open
          if (micOpen) {
            setLatency((p) => ({
              ...p,
              mic_open_to_first_partial_ms: Math.round(marksRef.current.first_partial! - micOpen),
            }))
          }
        }
        setProvisionalTranscript(transcript)
      }

      // Phase 2 — speculative reasoning on high-confidence interim STT before final.
      if (
        transcript &&
        !isFinal &&
        !agentSpeakingRef.current &&
        !speculativeRef.current &&
        !abortRef.current
      ) {
        const words = transcript.split(/\s+/).filter(Boolean)
        const highConfidence = confidence >= 0.85 || stability >= 0.9
        if (highConfidence && words.length >= 5) {
          void runSessionTurn(transcript, { speculative: true })
        }
      }

      if (type === "UtteranceEnd" || type === "utterance_end" || (isFinal && transcript)) {
        marksRef.current.utterance_end = performance.now()
        if (marksRef.current.first_partial) {
          setLatency((p) => ({
            ...p,
            partial_to_utterance_end_ms: Math.round(
              marksRef.current.utterance_end! - marksRef.current.first_partial!,
            ),
          }))
        }
        setPresence("understanding")
      }

      const eventPayload: Record<string, unknown> = {
        type:
          type === "UtteranceEnd" || type === "utterance_end"
            ? "utterance_end"
            : type === "SpeechStarted" || type === "speech_started"
              ? "speech_started"
              : "transcript",
        transcript,
        is_final: isFinal,
        speech_final: Boolean(data.speech_final),
        confidence,
        stability,
      }

      const tt = await postTurnTakingEvent({
        sensitivity: optsRef.current.sensitivity || "normal",
        event: eventPayload,
        state: turnStateRef.current,
      })
      if (!tt) {
        if (isFinal && transcript) {
          marksRef.current.first_partial = 0
          setProvisionalTranscript("")
          await runSessionTurn(transcript)
        }
        return
      }
      turnStateRef.current = tt.state
      const finalized = tt.finalized_transcript || (isFinal ? transcript : "")
      if (finalized) {
        marksRef.current.first_partial = 0
        setProvisionalTranscript("")
        await runSessionTurn(finalized)
      }
    },
    [bargeIn, runSessionTurn],
  )

  const start = useCallback(async () => {
    if (activeRef.current) return
    if (options.enabled === false) return
    await unlockVoicePlayback()
    marksRef.current = { mic_open: performance.now() }
    turnStateRef.current = null

    const tokenResult = await mintDeepgramLiveTokenDetailed()
    if (!tokenResult.ok) {
      setPresence("error")
      optsRef.current.onError?.(tokenResult.detail)
      return
    }
    const creds = tokenResult.creds

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      streamRef.current = stream
      analyserRef.current = createVoiceAnalyser()
      analyserRef.current.connectStream(stream)
      startRaf()

      const AC =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AC) throw new Error("AudioContext unavailable")
      const ctx = new AC()
      audioCtxRef.current = ctx
      if (ctx.state === "suspended") {
        await ctx.resume()
      }
      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      // Temporary JWT from /v1/auth/grant uses bearer subprotocol (not Token master key).
      const ws = new WebSocket(creds.ws_url, ["bearer", creds.access_token])
      ws.binaryType = "arraybuffer"
      wsRef.current = ws

      ws.onopen = () => {
        activeRef.current = true
        setIsActive(true)
        setPresence("listening")
      }
      ws.onmessage = (ev) => {
        void handleDeepgramMessage(ev)
      }
      ws.onerror = () => {
        setPresence("disconnected")
        optsRef.current.onError?.("Voice connection interrupted")
      }
      ws.onclose = () => {
        if (activeRef.current) setPresence("disconnected")
      }

      processor.onaudioprocess = (e) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        const input = e.inputBuffer.getChannelData(0)
        const pcm = downsampleTo16k(input, ctx.sampleRate)
        wsRef.current.send(pcm.buffer)
      }
      source.connect(processor)
      processor.connect(ctx.destination)
    } catch (err) {
      teardownMic()
      activeRef.current = false
      setIsActive(false)
      setPresence("error")
      optsRef.current.onError?.(
        err instanceof Error ? err.message : "Microphone permission denied",
      )
    }
  }, [handleDeepgramMessage, options.enabled, teardownMic])

  const stop = useCallback(() => {
    activeRef.current = false
    setIsActive(false)
    abortRef.current?.abort()
    stopPlayback()
    teardownMic()
    setPresence("idle")
    setProvisionalTranscript("")
  }, [stopPlayback, teardownMic])

  const toggle = useCallback(() => {
    if (activeRef.current) stop()
    else void start()
  }, [start, stop])

  useEffect(() => {
    return () => {
      activeRef.current = false
      abortRef.current?.abort()
      stopPlayback()
      teardownMic()
    }
  }, [stopPlayback, teardownMic])

  return {
    presence,
    levels,
    amplitude,
    provisionalTranscript,
    latency,
    isActive,
    playbackBlocked,
    start,
    stop,
    toggle,
    bargeIn,
    resumeBlockedPlayback,
    /** Inject a finalized utterance (tests / recovery) through the same session turn path. */
    submitFinalTranscript: runSessionTurn,
  }
}
