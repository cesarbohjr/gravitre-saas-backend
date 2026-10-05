"use client"

/**
 * Browser-level voice duplex harness — exercises the real useVoiceDuplexSession
 * hook. Gated like other /e2e routes.
 *
 * Two transports, chosen by `?transport=`:
 * - `http` (default): legacy HTTP duplex with a mocked Deepgram socket and
 *   mocked /api/voice fetches.
 * - `pipecat`: the production Pipecat path. Only /api/voice/status is mocked
 *   (to point the client at `?ws=`); the socket is real and talks to the
 *   Pipecat harness server, which runs the production pipeline builder with
 *   fake STT/TTS/LLM providers.
 */

import { useEffect, useState } from "react"
import { useVoiceDuplexSession } from "@/hooks/use-voice-duplex-session"
import { ORG_STORAGE_KEY } from "@/lib/org-context"

type HarnessTransport = "http" | "pipecat"

type HarnessMetrics = {
  pcmBytesSent: number
  wsOpen: boolean
  audioContextState: string
  sessionTurnRequested: boolean
  lastError: string
  sessionReady: boolean
  audioFramesReceived: number
  turnCompleteMessages: number
}

declare global {
  interface Window {
    __voiceDuplexHarness?: HarnessMetrics & {
      submitFinal: (text: string) => void
    }
    __GRAVITRE_VOICE_DUPLEX_HARNESS?: boolean
  }
}

const EMPTY_METRICS: HarnessMetrics = {
  pcmBytesSent: 0,
  wsOpen: false,
  audioContextState: "unknown",
  sessionTurnRequested: false,
  lastError: "",
  sessionReady: false,
  audioFramesReceived: 0,
  turnCompleteMessages: 0,
}

function readTransport(): { transport: HarnessTransport; wsBase: string } {
  const params = new URLSearchParams(window.location.search)
  const transport = params.get("transport") === "pipecat" ? "pipecat" : "http"
  return { transport, wsBase: params.get("ws") || "http://127.0.0.1:8799" }
}

export function VoiceDuplexHarness() {
  const [metrics, setMetrics] = useState<HarnessMetrics>(EMPTY_METRICS)
  const [config, setConfig] = useState<{ transport: HarnessTransport; wsBase: string } | null>(null)
  const [harnessReady, setHarnessReady] = useState(false)
  const [turn, setTurn] = useState<{ assistantText: string; userText: string; conversationId: string }>({
    assistantText: "",
    userText: "",
    conversationId: "",
  })

  useEffect(() => {
    setConfig(readTransport())
  }, [])

  // Installs the browser mocks. No "already patched" guard: React StrictMode in
  // dev mounts, cleans up, then mounts again, and the cleanup restores every
  // native API. The second run has to install the mocks again, or the page is
  // left unpatched and never reports ready.
  useEffect(() => {
    if (!config || typeof window === "undefined") return
    const { transport, wsBase } = config

    const pcm = {
      bytes: 0,
      open: false,
      sessionTurn: false,
      sessionReady: false,
      audioFrames: 0,
      turnComplete: 0,
    }
    const NativeWebSocket = window.WebSocket
    const origFetch = window.fetch
    const OrigAudioContext = window.AudioContext
    const origGUM = navigator.mediaDevices.getUserMedia
    const prevHarnessFlag = window.__GRAVITRE_VOICE_DUPLEX_HARNESS
    const prevOrg = window.localStorage.getItem(ORG_STORAGE_KEY)

    if (transport === "http") {
      window.WebSocket = class MockDeepgramWS {
        static CONNECTING = 0
        static OPEN = 1
        static CLOSING = 2
        static CLOSED = 3
        readyState = 1
        binaryType = "arraybuffer"
        onopen: ((ev: Event) => void) | null = null
        onmessage: ((ev: MessageEvent) => void) | null = null
        onerror: ((ev: Event) => void) | null = null
        onclose: ((ev: CloseEvent) => void) | null = null

        constructor(_url: string | URL, _protocols?: string | string[]) {
          pcm.open = true
          queueMicrotask(() => {
            this.onopen?.(new Event("open"))
            setTimeout(() => {
              const payload = JSON.stringify({
                type: "Results",
                is_final: true,
                speech_final: true,
                channel: { alternatives: [{ transcript: "hello harness", confidence: 0.99 }] },
              })
              this.onmessage?.({ data: payload } as MessageEvent)
            }, 120)
          })
        }

        send(data: ArrayBuffer | ArrayBufferView | Blob | string) {
          if (typeof data === "string") return
          if (data instanceof ArrayBuffer) {
            pcm.bytes += data.byteLength
          } else if (ArrayBuffer.isView(data)) {
            pcm.bytes += data.byteLength
          }
        }

        close() {
          pcm.open = false
          this.readyState = 3
        }
      } as unknown as typeof WebSocket
    } else {
      // Real socket to the Pipecat harness server, instrumented so the test can
      // see both directions of the production JSON/PCM protocol.
      class InstrumentedPipecatWS extends NativeWebSocket {
        constructor(url: string | URL, protocols?: string | string[]) {
          super(url, protocols)
          this.addEventListener("open", () => {
            pcm.open = true
          })
          this.addEventListener("close", () => {
            pcm.open = false
          })
          this.addEventListener("message", (ev: MessageEvent) => {
            try {
              const msg = JSON.parse(String(ev.data)) as { type?: string }
              if (msg.type === "session.ready") pcm.sessionReady = true
              if (msg.type === "audio") pcm.audioFrames += 1
              if (msg.type === "assistant_turn.complete") pcm.turnComplete += 1
            } catch {
              /* non-JSON frames are not part of this protocol */
            }
          })
        }

        send(data: string | ArrayBufferLike | Blob | ArrayBufferView) {
          if (typeof data === "string") {
            try {
              const msg = JSON.parse(data) as { type?: string; pcm16_b64?: string }
              if (msg.type === "audio" && typeof msg.pcm16_b64 === "string") {
                pcm.bytes += Math.floor((msg.pcm16_b64.length * 3) / 4)
              }
            } catch {
              /* ignore */
            }
          }
          super.send(data)
        }
      }
      window.WebSocket = InstrumentedPipecatWS as unknown as typeof WebSocket
      window.__GRAVITRE_VOICE_DUPLEX_HARNESS = true
      window.localStorage.setItem(
        ORG_STORAGE_KEY,
        JSON.stringify({ id: "00000000-0000-4000-8000-0000000000a1", name: "Voice Harness Org" }),
      )
    }

    // apiFetch calls global fetch. Install the mock before the user can click
    // Start so no request escapes to the /api proxy/backend during this guard.
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(typeof input === "string" ? input : input instanceof URL ? input : input.url)
      if (transport === "pipecat") {
        if (url.includes("/api/voice/status")) {
          return new Response(
            JSON.stringify({
              stt_enabled: true,
              tts_enabled: true,
              pipecat_enabled: true,
              pipecat_available: true,
              pipecat_ws_clients_accepted: true,
              pipecat_ws_hint: wsBase,
              pipecat_ws_path: "/api/voice/pipecat/ws",
            }),
            { status: 200, headers: { "content-type": "application/json" } },
          )
        }
        return origFetch(input, init)
      }
      if (url.includes("/api/voice/stt/live-token") || url.includes("/api/voice/stt/token")) {
        return new Response(
          JSON.stringify({
            ws_url: "wss://api.deepgram.com/v1/listen?model=nova-2",
            access_token: "harness-token",
            authorization: "Bearer harness-token",
            expires_in_seconds: 60,
            encoding: "linear16",
            sample_rate: 16000,
            provider: "deepgram",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        )
      }
      if (url.includes("/api/voice/session/turn")) {
        pcm.sessionTurn = true
        const body = '{"type":"voice.turn.complete","text":"Harness heard you.","transcript":"Harness heard you."}\n'
        return new Response(body, {
          status: 200,
          headers: { "content-type": "application/x-ndjson" },
        })
      }
      if (url.includes("/api/voice/turn-taking/event")) {
        return new Response(
          JSON.stringify({
            state: {},
            finalized_transcript: "hello harness",
          }),
          { status: 200, headers: { "content-type": "application/json" } },
        )
      }
      return origFetch(input, init)
    }

    // `state` lives on BaseAudioContext.prototype, so walk the chain for it.
    let nativeStateGetter: (() => AudioContextState) | undefined
    for (let proto: object | null = OrigAudioContext.prototype; proto; proto = Object.getPrototypeOf(proto)) {
      const descriptor = Object.getOwnPropertyDescriptor(proto, "state")
      if (descriptor?.get) {
        nativeStateGetter = descriptor.get as () => AudioContextState
        break
      }
    }

    const capture: { ctx: AudioContext | null } = { ctx: null }

    /**
     * Reproduces Chrome's autoplay policy: a freshly constructed AudioContext is
     * suspended. A capture graph that never calls resume() therefore starves its
     * ScriptProcessor and streams zero PCM — the exact regression under guard.
     * Without this, the harness click counts as a user gesture, the context
     * starts "running", and the bug cannot reproduce.
     */
    class AutoplayBlockedAudioContext extends OrigAudioContext {
      private blocked = true
      private readonly suspended: Promise<void>

      constructor(options?: AudioContextOptions) {
        super(options)
        this.suspended = OrigAudioContext.prototype.suspend.call(this)
        Object.defineProperty(this, "state", {
          configurable: true,
          get: () => (this.blocked ? "suspended" : (nativeStateGetter?.call(this) ?? "unknown")),
        })
        capture.ctx = this
      }

      async resume(): Promise<void> {
        await this.suspended.catch(() => {})
        this.blocked = false
        return OrigAudioContext.prototype.resume.call(this)
      }
    }

    window.AudioContext = AutoplayBlockedAudioContext as unknown as typeof AudioContext

    navigator.mediaDevices.getUserMedia = async () => {
      // Deliberately the unwrapped context: only the hook's capture graph is
      // subject to the autoplay block, so the assertion targets the hook.
      const ctx = new OrigAudioContext()
      const dest = ctx.createMediaStreamDestination()
      const osc = ctx.createOscillator()
      osc.frequency.value = 440
      osc.connect(dest)
      osc.start()
      await ctx.resume().catch(() => {})
      return dest.stream
    }

    setHarnessReady(true)

    const interval = window.setInterval(() => {
      setMetrics((prev) => ({
        pcmBytesSent: pcm.bytes,
        wsOpen: pcm.open,
        audioContextState: capture.ctx
          ? (nativeStateGetter?.call(capture.ctx) ?? "unknown")
          : "absent",
        sessionTurnRequested: pcm.sessionTurn,
        lastError: prev.lastError,
        sessionReady: pcm.sessionReady,
        audioFramesReceived: pcm.audioFrames,
        turnCompleteMessages: pcm.turnComplete,
      }))
    }, 100)

    return () => {
      window.clearInterval(interval)
      window.fetch = origFetch
      window.WebSocket = NativeWebSocket
      window.AudioContext = OrigAudioContext
      navigator.mediaDevices.getUserMedia = origGUM
      window.__GRAVITRE_VOICE_DUPLEX_HARNESS = prevHarnessFlag
      if (prevOrg === null) window.localStorage.removeItem(ORG_STORAGE_KEY)
      else window.localStorage.setItem(ORG_STORAGE_KEY, prevOrg)
      setHarnessReady(false)
    }
  }, [config])

  const duplex = useVoiceDuplexSession({
    forceHttpDuplex: config?.transport !== "pipecat",
    enabled: true,
    onError: (message) => {
      console.error("[voice-duplex-harness]", message)
      setMetrics((prev) => ({ ...prev, lastError: message }))
    },
    onConversationId: (id) => setTurn((prev) => ({ ...prev, conversationId: id })),
    onTurnComplete: (result) =>
      setTurn((prev) => ({
        assistantText: result.assistantText,
        userText: result.userText,
        conversationId: result.conversationId || prev.conversationId,
      })),
  })

  useEffect(() => {
    window.__voiceDuplexHarness = {
      ...metrics,
      submitFinal: (text: string) => {
        void duplex.submitFinalTranscript(text)
      },
    }
  }, [metrics, duplex])

  return (
    <div
      data-testid="voice-duplex-harness"
      data-ready={harnessReady ? "true" : "false"}
      data-transport={config?.transport ?? ""}
      data-presence={duplex.presence}
      data-active={duplex.isActive ? "true" : "false"}
      data-pcm-bytes={metrics.pcmBytesSent}
      data-ws-open={metrics.wsOpen ? "true" : "false"}
      data-session-turn={metrics.sessionTurnRequested ? "true" : "false"}
      data-session-ready={metrics.sessionReady ? "true" : "false"}
      data-audio-frames={metrics.audioFramesReceived}
      data-turn-complete-messages={metrics.turnCompleteMessages}
      data-user-text={turn.userText}
      data-assistant-text={turn.assistantText}
      data-conversation-id={turn.conversationId}
      data-last-error={metrics.lastError}
      data-capture-ctx-state={metrics.audioContextState}
      className="p-6"
    >
      <p className="text-sm">Voice duplex harness — presence: {duplex.presence}</p>
      <button
        type="button"
        data-testid="voice-duplex-start"
        disabled={!harnessReady}
        onClick={() => duplex.toggle()}
        className="mt-3 rounded-md border px-3 py-2 text-sm"
      >
        Toggle voice
      </button>
    </div>
  )
}
