"use client"

/**
 * Full-duplex voice session.
 *
 * Default product path (flag off): browser Deepgram STT → turn-taking →
 * POST /api/voice/session/turn → streaming MPEG TTS.
 *
 * When VOICE_PIPECAT_ENABLED (status.pipecat_enabled): browser PCM →
 * WS /api/voice/pipecat/ws (server Deepgram → CognitiveTurnKernel → ElevenLabs PCM).
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { createVoiceAnalyser, type VoiceAnalyserHandle } from "@/lib/voice-analyser"
import {
  ensureAudioOutputRunning,
  getSharedPlaybackContext,
  isResumableAudioState,
  preferPlayAndRecordAudioSession,
  unlockVoicePlayback,
} from "@/lib/voice-playback-unlock"
import {
  decideSocketFailure,
  isTerminalServerErrorClass,
  resolveFailureMessage,
} from "@/lib/voice-socket-reconnect"
import {
  recordVoiceSocketFailure,
  redactVoiceWsUrl,
  type VoiceSocketDiagnostic,
} from "@/lib/voice-socket-diagnostics"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import {
  buildPipecatVoiceWsUrl,
  encodePipecatAudioMessage,
  encodePipecatInterrupt,
  createPcm16StreamDecoder,
  encodePipecatPlaybackStarted,
  inspectPcm16Energy,
  shouldUsePipecatVoice,
} from "@/lib/pipecat-voice-client"
import {
  acquireVoiceMicrophoneStream,
  createVoiceMicCapture,
  type VoiceMicProcessorHandle,
  EchoLeakMonitor,
  voiceMicPhase1FlagsFromStatus,
  voiceMicPhase2FlagsFromStatus,
  type MicEffectiveSettings,
  type MicLevelSnapshot,
  type VoiceMicPhase1Flags,
  type VoiceMicPhase2Flags,
} from "@/lib/voice-mic-capture"
import type { MicFieldProfile } from "@/lib/voice-mic-devices"
import { postMicDiagnostics } from "@/lib/voice-mic-telemetry-client"
import { postVoiceOutputDiagnostics } from "@/lib/voice-output-telemetry-client"
import {
  createBufferSourcePcmPlayer,
  createVoicePcmPlayer,
  type VoicePcmPlayer,
} from "@/lib/voice-pcm-player"
import {
  cancelVoiceSessionTurn,
  getVoiceStatus,
  mintDeepgramLiveTokenDetailed,
  postTurnTakingEvent,
  streamVoiceSessionTurn,
  type VoiceSessionEvent,
  type VoiceStatus,
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
  /** Browser-side proof that audible playback was actually scheduled/started. */
  browser_audio_playback_started?: boolean
  /** The live duplex path owns delivery/recovery for this turn even before audio proof arrives. */
  duplex_transport_owned?: boolean
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

/** Phase 5: barge-in reconciliation — what the user actually heard. */
export type SpeechInterruptedInfo = {
  reconciledText: string
  draftChars: number
  droppedChars: number
  playbackOffsetMs: number | null
}

type Options = {
  enabled?: boolean
  conversationId?: string | null
  agentId?: string | null
  sensitivity?: string
  /** Preferred mic device (Phase 1 selector). */
  micDeviceId?: string | null
  /** near_field | far_field | auto — Phase 1 near/far tuning. */
  micProfileOverride?: MicFieldProfile
  /** E2E harness / forced legacy path — skip Pipecat even when the flag is on. */
  forceHttpDuplex?: boolean
  getHistory?: () => Array<{ role: string; content: string }>
  onUserFinal?: (text: string) => void
  onAssistantDelta?: (text: string) => void
  onSpeechInterrupted?: (info: SpeechInterruptedInfo) => void
  onTurnComplete?: (result: DuplexTurnResult) => void
  onError?: (message: string, billing?: boolean) => void
  /**
   * Recovery path when Pipecat produces assistant text but no audio frames.
   * The caller may synthesize that exact reply through the existing HTTP TTS
   * path; late Pipecat PCM for that turn is ignored to prevent double speech.
   */
  onAudioMissing?: (assistantText: string) => void
  onConversationId?: (id: string) => void
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
  const [orchestration, setOrchestration] = useState<"http" | "pipecat">("http")
  // Mic muted while the session stays connected. Previously the mic button called
  // toggle(), which tore the whole session down -- so "mute" ended the call, and the
  // orb was left reading "voice paused" beside "voice channel is live".
  const [micMuted, setMicMuted] = useState(false)
  const [micLevels, setMicLevels] = useState<MicLevelSnapshot | null>(null)
  const [micEffective, setMicEffective] = useState<MicEffectiveSettings | null>(null)
  const [micProfile, setMicProfile] = useState<string | null>(null)
  // Read by emitMicDiagnostics through refs so its identity never changes. If it
  // depended on this state, every level update would re-create teardownMic and
  // re-run the unmount cleanup below, tearing down a live session.
  const micLevelsRef = useRef<MicLevelSnapshot | null>(null)
  const micEffectiveRef = useRef<MicEffectiveSettings | null>(null)
  const micProfileRef = useRef<string | null>(null)
  micLevelsRef.current = micLevels
  micEffectiveRef.current = micEffective
  micProfileRef.current = micProfile
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null)

  const optsRef = useRef(options)
  optsRef.current = options

  const phase1FlagsRef = useRef<VoiceMicPhase1Flags>(voiceMicPhase1FlagsFromStatus(null))
  const phase2FlagsRef = useRef<VoiceMicPhase2Flags>(voiceMicPhase2FlagsFromStatus(null))
  const echoLeakRef = useRef(new EchoLeakMonitor())
  const voiceStatusRef = useRef<VoiceStatus | null>(null)
  const micSessionIdRef = useRef<string | null>(null)
  const telemetryTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const micProcessorRef = useRef<VoiceMicProcessorHandle | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const audioCtxSharedRef = useRef(false)
  const processorRef = useRef<AudioNode | null>(null)
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
  const micMutedRef = useRef(false)
  // Set before any deliberate ws.close(). Closing a CONNECTING socket fires
  // `onerror` (measured -- see scripts/probe-ws-error-conditions.mjs), which is how
  // a user-requested hangup surfaced as "Voice connection interrupted".
  const intentionalCloseRef = useRef(false)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const socketOpenedRef = useRef(false)
  // One failure can raise both `error` and `close`; this collapses them to a single
  // decision so a retry is not scheduled twice.
  const failureHandledRef = useRef(false)
  // The user wants a session. Distinct from activeRef, which only turns true once
  // the socket opens -- so a refused first connect would otherwise look like nobody
  // was waiting and be silently swallowed.
  const sessionWantedRef = useRef(false)
  // Re-entry points for a retry, assigned once the callbacks below exist.
  const startPipecatRef = useRef<(() => Promise<void>) | null>(null)
  const teardownMicRef = useRef<(() => void) | null>(null)
  // Mute survives a reconnect: it is the user's standing choice, not session state.
  const pendingMuteRestoreRef = useRef(false)
  // Retryable refusals (service_failure) explain themselves in an error frame and
  // are then followed by a close. Hold that explanation so the end of the ladder
  // can repeat it instead of replacing it with the generic string.
  const lastServerErrorRef = useRef<string | null>(null)
  // Mirrored into state as well as the ref: the ref is what the retry ladder
  // reads, but a ref cannot re-render the orb, and the orb is where a person
  // actually finds out why voice stopped. Without this the surface had no access
  // to the server's explanation at all.
  const [lastServerError, setLastServerError] = useState<string | null>(null)
  const lastServerErrorBillingRef = useRef(false)
  // Held for diagnostics only. Always pass it through redactVoiceWsUrl before it
  // leaves this module: the access token rides in the query string.
  const wsUrlRef = useRef<string | null>(null)
  const orchestrationRef = useRef<"http" | "pipecat">("http")
  // Pipecat reply playback (AudioWorklet player, or the buffer-source fallback).
  const pcmPlayerRef = useRef<VoicePcmPlayer | null>(null)
  const pcmBlockedQueueRef = useRef<Array<{ pcm: Int16Array; sampleRate: number }>>([])
  // One decoder per reply stream, so a sample split across two messages survives.
  const pcmDecoderRef = useRef(createPcm16StreamDecoder())
  const assistantTextRef = useRef("")
  const lastUserFinalRef = useRef("")
  // Pipecat keeps one websocket alive across many turns. Completion is per turn,
  // not per socket. This guard prevents a close event from re-dispatching a turn
  // already committed by the explicit assistant_turn.complete marker.
  const pipecatTurnCompletionDispatchedRef = useRef(false)
  // Physical-output watchdog: a healthy text turn with zero audio frames is not
  // a successful voice turn. Keep this separate from autoplay blocking: that
  // path has audio but cannot play it; this path means TTS/audio transport never
  // delivered anything to the browser.
  const audioReplyWatchdogRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const audioFramesReceivedRef = useRef(0)
  // performance.now() of the reply's first audio frame, for the playback.started report.
  const firstAudioReceivedAtRef = useRef<number | null>(null)
  // A non-empty PCM frame can still be digital silence. Keep transport receipt
  // separate from audible-energy receipt so silent provider output cannot disable
  // the recovery watchdog.
  const audibleAudioFramesRef = useRef(0)
  const maxPcmPeakRef = useRef(0)
  // Do not confuse server/provider TTFA with browser playback. This flag flips
  // only after WebAudio/HTMLAudio successfully starts on the client.
  const browserAudioPlaybackStartedRef = useRef(false)
  // Once the no-audio watchdog hands the turn to HTTP TTS, suppress any late
  // Pipecat PCM for that same turn so two voices never speak the reply at once.
  const audioFallbackTriggeredRef = useRef(false)
  // Output-path diagnostics stay browser-local. A running AudioContext can still
  // be suspended by the browser after the initial Talk gesture; listen for that
  // transition so the UI surfaces Enable sound instead of silently losing audio.
  const outputContextStateHandlerRef = useRef<(() => void) | null>(null)
  const outputFailureNotifiedRef = useRef(false)
  const speculativeRef = useRef<{
    text: string
    turnId: string
    startedAt: number
  } | null>(null)

  const clearAudioReplyWatchdog = useCallback(() => {
    if (audioReplyWatchdogRef.current) {
      clearTimeout(audioReplyWatchdogRef.current)
      audioReplyWatchdogRef.current = null
    }
  }, [])

  const emitOutputDiagnostic = useCallback(
    (
      event:
        | "audio_missing"
        | "audio_silent"
        | "output_unavailable"
        | "playback_blocked"
        | "playback_started"
        | "playback_recovered",
    ) => {
      const ctx = audioCtxRef.current
      void postVoiceOutputDiagnostics({
        session_id: micSessionIdRef.current,
        turn_id: turnIdRef.current,
        orchestration: orchestrationRef.current,
        event,
        audio_context_state: ctx?.state ?? null,
        pcm_frames_received: audioFramesReceivedRef.current,
        audible_pcm_frames: audibleAudioFramesRef.current,
        max_pcm_peak: maxPcmPeakRef.current,
        fallback_triggered: audioFallbackTriggeredRef.current,
        playback_blocked: playbackBlockedRef.current,
        browser_audio_playback_started: browserAudioPlaybackStartedRef.current,
      })
    },
    [],
  )


  const armAudioReplyWatchdog = useCallback(() => {
    clearAudioReplyWatchdog()
    audioReplyWatchdogRef.current = setTimeout(() => {
      audioReplyWatchdogRef.current = null
      if (
        sessionWantedRef.current &&
        activeRef.current &&
        assistantTextRef.current.trim() &&
        audibleAudioFramesRef.current === 0
      ) {
        const assistantText = assistantTextRef.current.trim()
        emitOutputDiagnostic(
          audioFramesReceivedRef.current > 0 ? "audio_silent" : "audio_missing",
        )
        const recover = optsRef.current.onAudioMissing
        if (recover && !audioFallbackTriggeredRef.current) {
          audioFallbackTriggeredRef.current = true
          // Keep the duplex mic's normal echo/barge-in behavior active while
          // HTTP TTS owns audible output for this turn.
          agentSpeakingRef.current = true
          setPresence("speaking")
          recover(assistantText)
          return
        }
        setPresence("error")
        optsRef.current.onError?.(
          "Voice reply arrived, but audible audio was not received. Try again.",
        )
      }
    }, 5000)
  }, [clearAudioReplyWatchdog, emitOutputDiagnostic])

  const stopPcmPlayback = useCallback(() => {
    // Short fade-out in the player rather than a hard stop: cutting a waveform
    // mid-cycle is itself a click.
    pcmPlayerRef.current?.flush()
    pcmBlockedQueueRef.current = []
    pcmDecoderRef.current.reset()
  }, [])

  const stopPlayback = useCallback(() => {
    clearAudioReplyWatchdog()
    audioFramesReceivedRef.current = 0
    audibleAudioFramesRef.current = 0
    maxPcmPeakRef.current = 0
    browserAudioPlaybackStartedRef.current = false
    audioFallbackTriggeredRef.current = false
    playingRef.current = false
    audioQueueRef.current = []
    playbackWiredRef.current = false
    playbackBlockedRef.current = false
    setPlaybackBlocked(false)
    stopPcmPlayback()
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
  }, [clearAudioReplyWatchdog, stopPcmPlayback])

  const stopMicTelemetry = useCallback(() => {
    if (telemetryTimerRef.current) {
      clearInterval(telemetryTimerRef.current)
      telemetryTimerRef.current = null
    }
  }, [])

  const emitMicDiagnostics = useCallback(
    (event: "session_start" | "periodic" | "session_end" | "echo_test") => {
      const flags = phase1FlagsRef.current
      if (!flags.micTelemetry && event !== "echo_test") return
      if (event === "echo_test" && !phase2FlagsRef.current.echoTestMode) return
      const levels = micProcessorRef.current?.getLastLevels() || micLevelsRef.current
      const micEffective = micEffectiveRef.current
      const micProfile = micProfileRef.current
      if (!levels && event === "periodic") return
      const echoLeak =
        event === "echo_test" ? echoLeakRef.current.reset() : undefined
      void postMicDiagnostics({
        session_id: micSessionIdRef.current || undefined,
        orchestration: orchestrationRef.current,
        mic_profile: micProfile || undefined,
        device_label: micEffective?.label,
        effective_settings: micEffective || undefined,
        metrics: {
          ...(levels || {}),
          ...(echoLeak ? { echo_leak: echoLeak } : {}),
        },
        event: event === "echo_test" ? "echo_test" : event,
      })
    },
    [],
  )

  // The player drained (or was flushed): the bot is no longer audible.
  const handlePcmActiveChange = useCallback(
    (playing: boolean) => {
      if (playing) return
      agentSpeakingRef.current = false
      if (phase2FlagsRef.current.echoTestMode) {
        emitMicDiagnostics("echo_test")
      }
      if (activeRef.current) setPresence("listening")
    },
    [emitMicDiagnostics],
  )

  const enqueuePcm = useCallback(
    (pcm: Int16Array, sampleRate: number) => {
      const ctx = audioCtxRef.current
      if (pcm.length === 0) return
      if (!ctx) {
        if (!outputFailureNotifiedRef.current) {
          outputFailureNotifiedRef.current = true
          emitOutputDiagnostic("output_unavailable")
          setPresence("error")
          optsRef.current.onError?.(
            "Voice audio output is unavailable in this browser. End the call and try again.",
          )
        }
        return
      }
      if (ctx.state !== "running" || playbackBlockedRef.current) {
        if (!playbackBlockedRef.current) emitOutputDiagnostic("playback_blocked")
        // Pipecat uses WebAudio PCM, not HTMLAudioElement.play(). Browsers can
        // suspend an AudioContext without throwing, which previously meant audio
        // frames were scheduled onto a silent clock and the user heard nothing.
        // Keep a bounded copy and surface the same explicit "Enable sound" recovery
        // used by the HTTP TTS path.
        pcmBlockedQueueRef.current.push({
          pcm: new Int16Array(pcm),
          sampleRate: sampleRate || 16000,
        })
        if (pcmBlockedQueueRef.current.length > 80) {
          pcmBlockedQueueRef.current.splice(0, pcmBlockedQueueRef.current.length - 80)
        }
        playbackBlockedRef.current = true
        setPlaybackBlocked(true)
        return
      }
      // Normally created with the session; the fallback covers a frame that
      // arrives before that (or a player lost to a context swap).
      let player = pcmPlayerRef.current
      if (!player) {
        player = createBufferSourcePcmPlayer(ctx, {
          onActiveChange: handlePcmActiveChange,
        })
        pcmPlayerRef.current = player
      }
      try {
        player.enqueue(pcm, sampleRate || 16000)
        if (!browserAudioPlaybackStartedRef.current) {
          emitOutputDiagnostic("playback_started")
          const receivedAt = firstAudioReceivedAtRef.current
          const ws = wsRef.current
          if (
            receivedAt != null &&
            orchestrationRef.current === "pipecat" &&
            ws &&
            ws.readyState === WebSocket.OPEN
          ) {
            // The player's scheduled start (worklet: its initial lead until
            // it reports the real start) on top of the time already queued.
            const origin = player.originTime()
            const leadMs = origin != null ? Math.max(0, origin - ctx.currentTime) * 1000 : 0
            const message = encodePipecatPlaybackStarted(performance.now() - receivedAt + leadMs)
            try {
              if (message) ws.send(message)
            } catch {
              /* latency evidence only */
            }
          }
          // Once per reply. A state update on every 40 ms chunk re-rendered the
          // voice UI ~25 times a second on the same thread that plays audio.
          setLatency((prev) => ({ ...prev, browser_audio_playback_started: true }))
        }
        browserAudioPlaybackStartedRef.current = true
      } catch {
        // A WebAudio scheduling failure used to drop this chunk silently even
        // though the server had delivered valid PCM. Hold the chunk and move the
        // session into the explicit sound-unlock recovery path instead.
        pcmBlockedQueueRef.current.unshift({
          pcm: new Int16Array(pcm),
          sampleRate: sampleRate || 16000,
        })
        playbackBlockedRef.current = true
        setPlaybackBlocked(true)
        if (!outputFailureNotifiedRef.current) {
          outputFailureNotifiedRef.current = true
          optsRef.current.onError?.(
            "Voice audio could not start. Tap Enable sound, then try again.",
          )
        }
        return
      }
      agentSpeakingRef.current = true
      setPresence("speaking")
    },
    [emitOutputDiagnostic, handlePcmActiveChange],
  )

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
      if (!browserAudioPlaybackStartedRef.current) {
        emitOutputDiagnostic("playback_started")
      }
      browserAudioPlaybackStartedRef.current = true
      setLatency((prev) => ({ ...prev, browser_audio_playback_started: true }))
    } catch (err) {
      playingRef.current = false
      URL.revokeObjectURL(url)
      const blocked =
        err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "AbortError")
      if (blocked) {
        emitOutputDiagnostic("playback_blocked")
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
  }, [emitOutputDiagnostic])

  /** Fresh user gesture (tap "Enable sound" / mic) — retry the held-back reply. */
  const resumeBlockedPlayback = useCallback(async () => {
    if (!playbackBlockedRef.current) return
    const unlocked = await unlockVoicePlayback()
    const ctx = audioCtxRef.current
    if (ctx && isResumableAudioState(ctx.state)) {
      await ensureAudioOutputRunning(ctx)
    }
    const outputRunning = !ctx || ctx.state === "running" || unlocked?.state === "running"
    if (!outputRunning) {
      setPlaybackBlocked(true)
      return
    }
    playbackBlockedRef.current = false
    outputFailureNotifiedRef.current = false
    setPlaybackBlocked(false)
    emitOutputDiagnostic("playback_recovered")
    const queuedPcm = pcmBlockedQueueRef.current.splice(0)
    for (const chunk of queuedPcm) {
      enqueuePcm(chunk.pcm, chunk.sampleRate)
    }
    void playNext()
  }, [emitOutputDiagnostic, enqueuePcm, playNext])
  const resumeBlockedPlaybackRef = useRef(resumeBlockedPlayback)
  resumeBlockedPlaybackRef.current = resumeBlockedPlayback

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

  const startMicTelemetry = useCallback(() => {
    stopMicTelemetry()
    const flags = phase1FlagsRef.current
    if (!flags.micTelemetry) return
    emitMicDiagnostics("session_start")
    telemetryTimerRef.current = setInterval(() => emitMicDiagnostics("periodic"), 5000)
  }, [emitMicDiagnostics, stopMicTelemetry])

  const setupVoiceMicrophone = useCallback(
    async (ctx: AudioContext) => {
      const flags = phase1FlagsRef.current
      preferPlayAndRecordAudioSession()
      const { stream, effective, tuning, profile } = await acquireVoiceMicrophoneStream({
        flags,
        deviceId: optsRef.current.micDeviceId,
        profileOverride: optsRef.current.micProfileOverride,
      })
      streamRef.current = stream
      setMicEffective(effective)
      setMicProfile(profile)
      return { stream, tuning, profile, prerollEnabled: flags.prerollV2 }
    },
    [],
  )

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

  /** Mute/unmute the mic without dropping the session or the WebSocket. */
  const applyMicMuted = useCallback((next: boolean) => {
    micMutedRef.current = next
    setMicMuted(next)
    // Disabling the track is what actually stops capture; the send guard below is
    // belt-and-braces so muted silence is never fed to STT, where a long run of it
    // can otherwise read as end-of-turn.
    streamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = !next
    })
    if (next) {
      setLevels(null)
      setAmplitude(null)
      setMicLevels(null)
    }
  }, [])

  const toggleMicMute = useCallback(() => {
    applyMicMuted(!micMutedRef.current)
  }, [applyMicMuted])

  const cancelReconnect = useCallback(() => {
    if (reconnectTimerRef.current != null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  /**
   * Single decision point for a socket that errored or closed.
   *
   * A deliberate hangup is ignored outright -- that is the "Voice connection
   * interrupted" fix. A genuine fault is retried a bounded number of times before
   * the user is told anything.
   */
  const handlePipecatSocketFailure = useCallback((diag?: VoiceSocketDiagnostic) => {
    if (failureHandledRef.current) return
    failureHandledRef.current = true

    // Why this logs instead of staying silent: the remaining unexplained report of
    // this toast could not be diagnosed from code alone, because the two facts that
    // separate the candidate causes -- the actual socket URL and the actual close
    // code -- exist only in the browser at the moment of failure. Recording them
    // means the next occurrence explains itself instead of requiring the user to
    // read DevTools by hand.
    recordVoiceSocketFailure({
      event: diag?.event ?? "error",
      url: redactVoiceWsUrl(wsUrlRef.current),
      code: diag?.code,
      reason: diag?.reason,
      wasClean: diag?.wasClean,
      everOpened: socketOpenedRef.current,
      attempt: reconnectAttemptRef.current,
      intentional: intentionalCloseRef.current,
      sessionWanted: sessionWantedRef.current,
      lastServerError: lastServerErrorRef.current,
    })

    const decision = decideSocketFailure({
      intentional: intentionalCloseRef.current,
      sessionActive: sessionWantedRef.current,
      attempt: reconnectAttemptRef.current,
      everOpened: socketOpenedRef.current,
    })

    if (decision.action === "ignore") return

    if (decision.action === "reconnect") {
      reconnectAttemptRef.current = decision.attempt
      // Presence is left alone here on purpose: retries are sub-second, and
      // flashing "disconnected" for a blip the user never notices is its own bug.
      cancelReconnect()
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        if (!sessionWantedRef.current) return
        // Release the dead socket, mic and AudioContext first: startPipecat
        // allocates fresh ones and would otherwise leak the old set every retry.
        // Mute is the user's standing choice, so it survives the reconnect.
        const wasMuted = micMutedRef.current
        teardownMicRef.current?.()
        pendingMuteRestoreRef.current = wasMuted
        void startPipecatRef.current?.()
      }, decision.delayMs)
      return
    }

    setPresence("disconnected")
    optsRef.current.onError?.(
      resolveFailureMessage(lastServerErrorRef.current),
      lastServerErrorBillingRef.current,
    )
  }, [cancelReconnect])

  const teardownMic = useCallback(() => {
    // Everything below is a deliberate teardown, so mark intent before closing the
    // socket. Without this the close() below re-enters the failure handler.
    intentionalCloseRef.current = true
    cancelReconnect()
    stopRaf()
    stopMicTelemetry()
    emitMicDiagnostics("session_end")
    micProcessorRef.current?.dispose()
    micProcessorRef.current = null
    micSessionIdRef.current = null
    try {
      processorRef.current?.disconnect()
    } catch {
      /* ignore */
    }
    processorRef.current = null
    pcmPlayerRef.current?.dispose()
    pcmPlayerRef.current = null
    try {
      const outputCtx = audioCtxRef.current
      const stateHandler = outputContextStateHandlerRef.current
      if (outputCtx && stateHandler) {
        outputCtx.removeEventListener("statechange", stateHandler)
      }
      outputContextStateHandlerRef.current = null
      if (!audioCtxSharedRef.current) {
        outputCtx?.close()
      }
    } catch {
      /* ignore */
    }
    audioCtxRef.current = null
    audioCtxSharedRef.current = false
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
    setMicLevels(null)
    setMicEffective(null)
    setMicProfile(null)
    // A new session must never start silently muted.
    micMutedRef.current = false
    setMicMuted(false)
  }, [cancelReconnect, emitMicDiagnostics, stopMicTelemetry])

  const bargeIn = useCallback(async () => {
    const t0 = performance.now()
    // Capture the heard-audio offset BEFORE stopPlayback clears the PCM origin.
    // Played-audio reconciliation depends on this boundary; the old order always
    // sent undefined even when audio had been playing.
    const ctxBeforeStop = audioCtxRef.current
    const pcmOriginBeforeStop = pcmPlayerRef.current?.originTime() ?? null
    const playbackOffsetMs =
      ctxBeforeStop && pcmOriginBeforeStop != null
        ? Math.max(0, Math.round((ctxBeforeStop.currentTime - pcmOriginBeforeStop) * 1000))
        : undefined
    setPresence("interrupted")
    agentSpeakingRef.current = false
    stopPlayback()
    abortRef.current?.abort()
    abortRef.current = null
    if (orchestrationRef.current === "pipecat") {
      const ws = wsRef.current
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(encodePipecatInterrupt({ playbackOffsetMs }))
        } catch {
          /* ignore */
        }
      }
    } else {
      const tid = turnIdRef.current
      if (tid) {
        await cancelVoiceSessionTurn({
          turnId: tid,
          conversationId: optsRef.current.conversationId,
          reason: "barge_in",
        }).catch(() => false)
      }
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
      const stage: DuplexLatencyStages = { browser_audio_playback_started: false }
      browserAudioPlaybackStartedRef.current = false

      const dispatchTurnComplete = () => {
        if (completionDispatched) return
        completionDispatched = true
        stage.browser_audio_playback_started = browserAudioPlaybackStartedRef.current
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
        stage.browser_audio_playback_started = browserAudioPlaybackStartedRef.current
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

  const startPipecat = useCallback(async () => {
    // getVoiceStatus() already can't throw (internally caught). buildPipecatVoiceWsUrl()
    // returns `{ error }` for the expected auth/org gaps, but getSelectedOrgFromStorage()
    // reading corrupted localStorage — or anything else unforeseen — is still a bare
    // `await` with no catch of its own. Belt-and-suspenders: the outer try below (which
    // already wraps the mic/WS setup) now wraps this too, so no path through
    // startPipecat() can throw silently past `void start()`'s caller.
    const status = await getVoiceStatus(true)
    voiceStatusRef.current = status
    setVoiceStatus(status)
    phase1FlagsRef.current = voiceMicPhase1FlagsFromStatus(status)
    phase2FlagsRef.current = voiceMicPhase2FlagsFromStatus(status)
    const built = await buildPipecatVoiceWsUrl({
      status,
      agentId: optsRef.current.agentId,
      conversationId: optsRef.current.conversationId,
    })
    if ("error" in built) {
      setPresence("error")
      optsRef.current.onError?.(built.error)
      return
    }

    try {
      const AC =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!AC) throw new Error("AudioContext unavailable")

      // Reuse the output context that was unlocked synchronously from the user's
      // Talk gesture in start(). The old path created a second AudioContext only
      // after status/auth awaits; on Safari/iOS that second context can remain
      // suspended even though microphone capture and the websocket are healthy.
      const sharedOutput = getSharedPlaybackContext()
      const ctx = sharedOutput ?? new AC()
      audioCtxSharedRef.current = Boolean(sharedOutput && ctx === sharedOutput)
      audioCtxRef.current = ctx
      outputFailureNotifiedRef.current = false
      const onOutputStateChange = () => {
        if (audioCtxRef.current !== ctx) return
        if (!sessionWantedRef.current) return
        if (ctx.state === "running") {
          // iOS hands output back after an interruption (mic start, call, route
          // change) without a tap; recover on our own instead of waiting for one.
          if (playbackBlockedRef.current) void resumeBlockedPlaybackRef.current?.()
          return
        }
        // Try to resume before asking for a tap: an "interrupted" context usually
        // resumes by itself, and only a real autoplay gate needs Enable sound.
        void ensureAudioOutputRunning(ctx).then((running) => {
          if (running || audioCtxRef.current !== ctx || !sessionWantedRef.current) return
          playbackBlockedRef.current = true
          setPlaybackBlocked(true)
        })
      }
      outputContextStateHandlerRef.current = onOutputStateChange
      ctx.addEventListener("statechange", onOutputStateChange)
      await ensureAudioOutputRunning(ctx)
      pcmDecoderRef.current.reset()
      pcmPlayerRef.current?.dispose()
      pcmPlayerRef.current = null
      // The worklet module loads while the mic permission prompt is up.
      const playerReady = createVoicePcmPlayer(ctx, { onActiveChange: handlePcmActiveChange })

      const { stream, tuning, prerollEnabled } = await setupVoiceMicrophone(ctx)
      // Opening the mic is what interrupts output on iOS. Resume after it, and
      // only then decide whether the person has to tap Enable sound.
      if (!(await ensureAudioOutputRunning(ctx)) && audioCtxRef.current === ctx) {
        playbackBlockedRef.current = true
        setPlaybackBlocked(true)
      }
      const player = await playerReady
      if (audioCtxRef.current !== ctx) {
        // Torn down while we waited: release what this attempt acquired.
        player.dispose()
        // This attempt's mic is ours to stop even if a newer start already
        // replaced streamRef; only clear the ref when it still points here.
        stream.getTracks().forEach((t) => t.stop())
        if (streamRef.current === stream) streamRef.current = null
        return
      }
      pcmPlayerRef.current = player
      // Re-apply a mute the user set before a reconnect dropped the old track.
      if (pendingMuteRestoreRef.current) {
        pendingMuteRestoreRef.current = false
        applyMicMuted(true)
      }
      analyserRef.current = createVoiceAnalyser()
      analyserRef.current.connectStream(stream)
      startRaf()
      startMicTelemetry()

      wsUrlRef.current = built.url
      const ws = new WebSocket(built.url)
      wsRef.current = ws
      // Per-attempt state. `intentionalCloseRef` must be cleared here: a previous
      // teardown (including the one a reconnect performs) leaves it set, which would
      // make the next genuine fault look deliberate and be silently ignored.
      intentionalCloseRef.current = false
      failureHandledRef.current = false
      socketOpenedRef.current = false
      assistantTextRef.current = ""
      lastUserFinalRef.current = ""

      ws.onopen = () => {
        activeRef.current = true
        socketOpenedRef.current = true
        // A clean open retires the retry ladder, so a later unrelated blip gets its
        // own full budget instead of inheriting a spent one.
        reconnectAttemptRef.current = 0
        // A live socket also retires the previous attempt's explanation; keeping
        // it would let a stale reason surface after an unrelated later failure.
        lastServerErrorRef.current = null
        setLastServerError(null)
        lastServerErrorBillingRef.current = false
        setIsActive(true)
        setPresence("listening")
      }

      ws.onmessage = (ev) => {
        let msg: Record<string, unknown>
        try {
          msg = JSON.parse(String(ev.data)) as Record<string, unknown>
        } catch {
          return
        }
        const kind = String(msg.type || "")
        if (kind === "session.ready") {
          const cid = typeof msg.conversation_id === "string" ? msg.conversation_id : null
          if (cid) optsRef.current.onConversationId?.(cid)
          return
        }
        if (kind === "error") {
          const err = String(msg.error || "Voice session failed")
          const billing = String(msg.error_class || "") === "billing"
          // A refusal (bad token, no seat, voice off) is settled: the close that
          // follows must not be retried, or the user waits out the whole ladder
          // before seeing an answer that will not change.
          if (isTerminalServerErrorClass(msg.error_class)) {
            sessionWantedRef.current = false
            cancelReconnect()
          } else {
            // Retryable, so a close is coming and the ladder will run. Keep the
            // reason so the final toast repeats it rather than degrading to
            // "Voice connection interrupted".
            lastServerErrorRef.current = err
            setLastServerError(err)
            lastServerErrorBillingRef.current = billing
          }
          optsRef.current.onError?.(err, billing)
          setPresence("error")
          return
        }
        if (kind === "transcript") {
          const text = String(msg.text || "").trim()
          if (!text) return
          setProvisionalTranscript(text)
          if (msg.final) {
            lastUserFinalRef.current = text
            browserAudioPlaybackStartedRef.current = false
            audioFallbackTriggeredRef.current = false
            setLatency((prev) => ({ ...prev, browser_audio_playback_started: false }))
            optsRef.current.onUserFinal?.(text)
            setProvisionalTranscript("")
            setPresence("thinking")
            clearAudioReplyWatchdog()
            audioFramesReceivedRef.current = 0
            firstAudioReceivedAtRef.current = null
            audibleAudioFramesRef.current = 0
            maxPcmPeakRef.current = 0
            assistantTextRef.current = ""
            turnIdRef.current = null
            pipecatTurnCompletionDispatchedRef.current = false
          } else if (agentSpeakingRef.current) {
            void bargeIn()
          }
          return
        }
        if (kind === "assistant_text") {
          const delta = String(msg.delta || "")
          if (!delta) return
          const firstAssistantText = assistantTextRef.current.length === 0
          assistantTextRef.current += delta
          if (firstAssistantText && audibleAudioFramesRef.current === 0) {
            armAudioReplyWatchdog()
          }
          optsRef.current.onAssistantDelta?.(assistantTextRef.current)
          return
        }
        if (kind === "assistant_turn.complete") {
          if (pipecatTurnCompletionDispatchedRef.current) return
          const fallbackText = String(msg.text || "").trim()
          const assistantText = assistantTextRef.current.trim() || fallbackText
          const turnId = String(msg.turn_id || "").trim() || null
          const completedConversationId =
            typeof msg.conversation_id === "string" && msg.conversation_id.trim()
              ? msg.conversation_id.trim()
              : optsRef.current.conversationId || null
          if (completedConversationId && completedConversationId !== optsRef.current.conversationId) {
            optsRef.current.conversationId = completedConversationId
            optsRef.current.onConversationId?.(completedConversationId)
          }
          turnIdRef.current = turnId
          pipecatTurnCompletionDispatchedRef.current = true
          optsRef.current.onTurnComplete?.({
            userText: lastUserFinalRef.current,
            assistantText,
            conversationId: completedConversationId,
            turnId,
            cancelled: false,
            events: [],
            latency: {
              browser_audio_playback_started: browserAudioPlaybackStartedRef.current,
              duplex_transport_owned: true,
            },
          })
          return
        }
        if (kind === "speech.interrupted") {
          // The server only sends this for a real barge-in. Drop the audio
          // already queued here (up to the jitter lead) so the bot stops the
          // moment the user cuts in, not after the buffer drains.
          if (agentSpeakingRef.current || pcmPlayerRef.current?.isActive()) {
            stopPcmPlayback()
            agentSpeakingRef.current = false
            if (activeRef.current) setPresence("listening")
          }
          // Phase 5: reconcile the visible/stored assistant text down to the
          // portion that was actually spoken aloud. Without this the drafted
          // tail the user never heard is replayed as history next turn.
          if (msg.reconcile_played_audio !== true) return
          const reconciled = String(msg.reconciled_text ?? "")
          if (reconciled.length >= assistantTextRef.current.length) return
          assistantTextRef.current = reconciled
          optsRef.current.onAssistantDelta?.(reconciled)
          optsRef.current.onSpeechInterrupted?.({
            reconciledText: reconciled,
            draftChars: Number(msg.draft_chars) || 0,
            droppedChars: Number(msg.dropped_chars) || 0,
            playbackOffsetMs:
              typeof msg.playback_offset_ms === "number" ? msg.playback_offset_ms : null,
          })
          return
        }
        if (kind === "audio" && typeof msg.pcm16_b64 === "string") {
          // HTTP TTS owns this turn after the no-audio watchdog fires. A late
          // provider frame must not create overlapping speech.
          if (audioFallbackTriggeredRef.current) return
          const pcm = pcmDecoderRef.current.decode(msg.pcm16_b64)
          if (pcm.length > 0) {
            if (firstAudioReceivedAtRef.current == null) {
              firstAudioReceivedAtRef.current = performance.now()
            }
            audioFramesReceivedRef.current += 1
            const energy = inspectPcm16Energy(pcm)
            maxPcmPeakRef.current = Math.max(maxPcmPeakRef.current, energy.peak)
            if (energy.audible) {
              audibleAudioFramesRef.current += 1
              clearAudioReplyWatchdog()
            }
          }
          enqueuePcm(pcm, Number(msg.sample_rate) || 16000)
        }
      }

      // error and close share one handler because which of them fires is not a
      // reliable signal (Node's ws and browsers disagree on unclean teardown), and
      // both can fire for a single failure. Intent decides, and this runs once.
      ws.onerror = () => handlePipecatSocketFailure({ event: "error" })
      ws.onclose = (ev) => {
        const wasIntentional = intentionalCloseRef.current
        // The close code is the fact that separates the remaining candidate
        // causes, and it exists nowhere else, so hand it to the diagnostic.
        handlePipecatSocketFailure({
          event: "close",
          code: ev.code,
          reason: ev.reason,
          wasClean: ev.wasClean,
        })
        // A completed turn is still worth reporting when the user hung up; on a
        // failure being retried it would end the turn mid-reconnect.
        if (
          !pipecatTurnCompletionDispatchedRef.current &&
          (wasIntentional || reconnectTimerRef.current == null) &&
          (lastUserFinalRef.current || assistantTextRef.current)
        ) {
          optsRef.current.onTurnComplete?.({
            userText: lastUserFinalRef.current,
            assistantText: assistantTextRef.current.trim(),
            conversationId: optsRef.current.conversationId || null,
            turnId: null,
            cancelled: false,
            events: [],
            latency: {
              browser_audio_playback_started: browserAudioPlaybackStartedRef.current,
            },
          })
        }
      }

      const mic = await createVoiceMicCapture({
        ctx,
        stream,
        tuning,
        prerollEnabled,
        silentTapV2: phase2FlagsRef.current.silentTapV2,
        onPcm: (pcm) => {
          if (micMutedRef.current) return
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
          try {
            wsRef.current.send(encodePipecatAudioMessage(pcm, 16000, 1))
          } catch {
            /* ignore */
          }
        },
        onLevels: (snapshot) => {
          setMicLevels(snapshot)
          if (phase2FlagsRef.current.echoTestMode && agentSpeakingRef.current) {
            echoLeakRef.current.observe(snapshot.rms)
          }
        },
        // Pipecat owns acoustic interruption classification server-side.
        // Do not let raw browser energy stop playback before Flux +
        // BackchannelAwareUserTurnStartStrategy can distinguish "mm-hm" from
        // a genuine interruption. Manual UI bargeIn() remains available.
        agentSpeaking: () => agentSpeakingRef.current,
      })
      if (audioCtxRef.current !== ctx) {
        mic.dispose()
        stream.getTracks().forEach((t) => t.stop())
        if (streamRef.current === stream) streamRef.current = null
        return
      }
      micProcessorRef.current = mic
      processorRef.current = mic.processor
    } catch (err) {
      // A throw here is a local setup failure (mic permission, AudioContext), not a
      // transport fault, so it is reported directly and never retried.
      sessionWantedRef.current = false
      teardownMic()
      activeRef.current = false
      setIsActive(false)
      setPresence("error")
      optsRef.current.onError?.(
        err instanceof Error ? err.message : "Microphone permission denied",
      )
    }
  }, [applyMicMuted, armAudioReplyWatchdog, bargeIn, cancelReconnect, clearAudioReplyWatchdog, enqueuePcm, handlePcmActiveChange, handlePipecatSocketFailure, setupVoiceMicrophone, startMicTelemetry, stopPcmPlayback, teardownMic])

  // Assigned after definition so handlePipecatSocketFailure can re-enter these
  // without a circular useCallback dependency.
  startPipecatRef.current = startPipecat
  teardownMicRef.current = teardownMic

  const start = useCallback(async () => {
    if (activeRef.current) return
    if (options.enabled === false) return
    // Outer guard for the whole function: toggle() invokes this as `void start()`,
    // so any uncaught throw anywhere below — a slow/erroring getVoiceStatus,
    // mintDeepgramLiveTokenDetailed, buildPipecatVoiceWsUrl, or unlockVoicePlayback —
    // used to vanish completely: no presence change, no onError, no console trace a
    // typical user would notice. The orb just sat there looking normal, connected to
    // nothing. This is the single top-level safety net; the inner try below (mic +
    // WebSocket setup) still owns its own specific error messaging and is unchanged.
    try {
      // The user has asked for a session. Set before any await so a connect that
      // fails before the socket opens is still recognised as wanted, and retried,
      // rather than read as an orphaned failure and dropped in silence.
      sessionWantedRef.current = true
      reconnectAttemptRef.current = 0
      pendingMuteRestoreRef.current = false
      await unlockVoicePlayback()
      marksRef.current = { mic_open: performance.now() }
      turnStateRef.current = null
      micSessionIdRef.current =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `mic-${Date.now()}`

      const status = options.forceHttpDuplex ? null : await getVoiceStatus(true)
      voiceStatusRef.current = status
      setVoiceStatus(status)
      phase1FlagsRef.current = voiceMicPhase1FlagsFromStatus(status)
      phase2FlagsRef.current = voiceMicPhase2FlagsFromStatus(status)
      const usePipecat = !options.forceHttpDuplex && shouldUsePipecatVoice(status)
      orchestrationRef.current = usePipecat ? "pipecat" : "http"
      setOrchestration(orchestrationRef.current)

      if (usePipecat) {
        await startPipecat()
        return
      }

      const tokenResult = await mintDeepgramLiveTokenDetailed()
      if (!tokenResult.ok) {
        setPresence("error")
        optsRef.current.onError?.(tokenResult.detail)
        return
      }
      const creds = tokenResult.creds

      try {
        const AC =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        if (!AC) throw new Error("AudioContext unavailable")
        const sharedOutput = getSharedPlaybackContext()
        const ctx = sharedOutput ?? new AC()
        audioCtxSharedRef.current = Boolean(sharedOutput && ctx === sharedOutput)
        audioCtxRef.current = ctx
        await ensureAudioOutputRunning(ctx)

        const { stream, tuning, prerollEnabled } = await setupVoiceMicrophone(ctx)
        if (!(await ensureAudioOutputRunning(ctx)) && audioCtxRef.current === ctx) {
          playbackBlockedRef.current = true
          setPlaybackBlocked(true)
        }
        analyserRef.current = createVoiceAnalyser()
        analyserRef.current.connectStream(stream)
        startRaf()
        startMicTelemetry()

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
          // handleDeepgramMessage now degrades gracefully on its own internal
          // failures (postTurnTakingEvent is hardened not to throw), but this
          // .catch is a second, cheaper-than-nothing safety net: anything still
          // unforeseen surfaces as a real error instead of a dropped turn.
          handleDeepgramMessage(ev).catch((err) => {
            optsRef.current.onError?.(
              err instanceof Error ? err.message : "Voice turn failed unexpectedly",
            )
          })
        }
        ws.onerror = () => {
          // Same intent guard as the Pipecat path: closing this socket while it is
          // still CONNECTING raises `error`, and a hangup the user asked for must
          // not be reported as a fault.
          //
          // No reconnect ladder here on purpose. This leg talks straight to Deepgram
          // with a short-lived minted token, so a retry needs a fresh mint through
          // start() rather than a socket re-dial. Pipecat is the production path
          // (VOICE_PIPECAT_ENABLED=true); this is the legacy fallback.
          if (intentionalCloseRef.current || !sessionWantedRef.current) return
          setPresence("disconnected")
          optsRef.current.onError?.("Voice connection interrupted")
        }
        ws.onclose = () => {
          if (activeRef.current) setPresence("disconnected")
        }

        const mic = await createVoiceMicCapture({
          ctx,
          stream,
          tuning,
          prerollEnabled,
          silentTapV2: phase2FlagsRef.current.silentTapV2,
          onPcm: (pcm) => {
            if (micMutedRef.current) return
            if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
            wsRef.current.send(pcm.buffer)
          },
          onLevels: (snapshot) => {
            setMicLevels(snapshot)
            if (phase2FlagsRef.current.echoTestMode && agentSpeakingRef.current) {
              echoLeakRef.current.observe(snapshot.rms)
            }
          },
        })
        if (audioCtxRef.current !== ctx) {
          mic.dispose()
          return
        }
        micProcessorRef.current = mic
        processorRef.current = mic.processor
      } catch (err) {
        teardownMic()
        activeRef.current = false
        setIsActive(false)
        setPresence("error")
        optsRef.current.onError?.(
          err instanceof Error ? err.message : "Microphone permission denied",
        )
      }
    } catch (err) {
      teardownMic()
      activeRef.current = false
      setIsActive(false)
      setPresence("error")
      optsRef.current.onError?.(
        err instanceof Error ? err.message : "Voice session failed to start. Try again.",
      )
    }
  }, [handleDeepgramMessage, options.enabled, options.forceHttpDuplex, setupVoiceMicrophone, startMicTelemetry, startPipecat, teardownMic])

  const stop = useCallback(() => {
    // Clearing intent first is what makes the resulting ws.close() silent: the
    // failure handler sees a session nobody is waiting on and neither retries nor
    // toasts. This is the user-initiated half of the interrupted-toast fix.
    sessionWantedRef.current = false
    reconnectAttemptRef.current = 0
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

  const stopPlaybackRef = useRef(stopPlayback)
  stopPlaybackRef.current = stopPlayback

  // Unmount only. Through refs, with no deps: if this cleanup were keyed on the
  // callbacks, any change in their identity would run it mid-session and kill
  // the live mic and socket.
  useEffect(() => {
    return () => {
      // Unmount is deliberate: no retry, no toast on the way out.
      sessionWantedRef.current = false
      activeRef.current = false
      abortRef.current?.abort()
      stopPlaybackRef.current()
      teardownMicRef.current?.()
    }
  }, [])

  return {
    presence,
    lastServerError,
    levels,
    amplitude,
    provisionalTranscript,
    latency,
    isActive,
    playbackBlocked,
    orchestration,
    micLevels,
    micEffective,
    micProfile,
    voiceStatus,
    micMuted,
    toggleMicMute,
    setMicMuted: applyMicMuted,
    start,
    stop,
    toggle,
    bargeIn,
    resumeBlockedPlayback,
    /** Inject a finalized utterance (tests / recovery). */
    submitFinalTranscript: async (text: string, opts?: { speculative?: boolean }) => {
      if (orchestrationRef.current === "pipecat") {
        const ws = wsRef.current
        if (ws && ws.readyState === WebSocket.OPEN) {
          const trimmed = text.trim()
          if (!trimmed) return
          lastUserFinalRef.current = trimmed
          optsRef.current.onUserFinal?.(trimmed)
          setPresence("thinking")
          assistantTextRef.current = ""
          ws.send(JSON.stringify({ type: "text", text: trimmed }))
        }
        return
      }
      await runSessionTurn(text, opts)
    },
  }
}
