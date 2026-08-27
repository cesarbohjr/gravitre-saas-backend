"use client"

/**
 * Browser-level voice duplex harness — exercises the real useVoiceDuplexSession
 * hook with mocked Deepgram WS + live-token API. Gated like other /e2e routes.
 */

import { useEffect, useRef, useState } from "react"
import { useVoiceDuplexSession } from "@/hooks/use-voice-duplex-session"

type HarnessMetrics = {
  pcmBytesSent: number
  wsOpen: boolean
  audioContextState: string
  sessionTurnRequested: boolean
}

declare global {
  interface Window {
    __voiceDuplexHarness?: HarnessMetrics & {
      submitFinal: (text: string) => void
    }
  }
}

export function VoiceDuplexHarness() {
  const [metrics, setMetrics] = useState<HarnessMetrics>({
    pcmBytesSent: 0,
    wsOpen: false,
    audioContextState: "unknown",
    sessionTurnRequested: false,
  })
  const patchedRef = useRef(false)

  useEffect(() => {
    if (patchedRef.current || typeof window === "undefined") return
    patchedRef.current = true

    const pcm = { bytes: 0, open: false, ctxState: "unknown", sessionTurn: false }

    window.WebSocket = class MockDeepgramWS {
      static OPEN = 1
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

    const origFetch = window.fetch.bind(window)
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(typeof input === "string" ? input : input instanceof URL ? input : input.url)
      if (url.includes("/api/voice/stt/live-token")) {
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

    const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      const ctx = new AC!()
      pcm.ctxState = ctx.state
      const dest = ctx.createMediaStreamDestination()
      const osc = ctx.createOscillator()
      osc.frequency.value = 440
      osc.connect(dest)
      osc.start()
      void ctx.resume().then(() => {
        pcm.ctxState = ctx.state
      })
      return dest.stream
    }

    const interval = window.setInterval(() => {
      setMetrics({
        pcmBytesSent: pcm.bytes,
        wsOpen: pcm.open,
        audioContextState: pcm.ctxState,
        sessionTurnRequested: pcm.sessionTurn,
      })
    }, 100)

    return () => {
      window.clearInterval(interval)
      window.fetch = origFetch
      navigator.mediaDevices.getUserMedia = origGUM
    }
  }, [])

  const duplex = useVoiceDuplexSession({
    enabled: true,
    onError: (message) => {
      console.error("[voice-duplex-harness]", message)
    },
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
      data-presence={duplex.presence}
      data-active={duplex.isActive ? "true" : "false"}
      data-pcm-bytes={metrics.pcmBytesSent}
      data-ws-open={metrics.wsOpen ? "true" : "false"}
      data-session-turn={metrics.sessionTurnRequested ? "true" : "false"}
      className="p-6"
    >
      <p className="text-sm">Voice duplex harness — presence: {duplex.presence}</p>
      <button
        type="button"
        data-testid="voice-duplex-start"
        onClick={() => duplex.toggle()}
        className="mt-3 rounded-md border px-3 py-2 text-sm"
      >
        Toggle voice
      </button>
    </div>
  )
}
