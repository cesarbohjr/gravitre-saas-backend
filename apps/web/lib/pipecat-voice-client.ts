/**
 * Pipecat voice WebSocket helpers — browser PCM ↔ server Deepgram/Cognitive/ElevenLabs.
 */

import { getAccessToken } from "@/lib/auth-context"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { PRODUCTION_API_URL } from "@/lib/public-urls"
import type { VoiceStatus } from "@/lib/tier1-voice-client"

export type PipecatOutboundAudio = {
  type: "audio"
  pcm16_b64: string
  sample_rate?: number
  num_channels?: number
}

export type PipecatServerMessage =
  | { type: "session.ready"; conversation_id?: string | null; architecture?: string; cognitive_path?: string }
  | { type: "audio"; pcm16_b64: string; sample_rate?: number; num_channels?: number }
  | { type: "transcript"; text?: string; final?: boolean }
  | { type: "assistant_text"; delta?: string }
  | { type: "error"; error?: string; error_class?: string }
  | { type: string; [key: string]: unknown }

function httpBaseToWs(base: string): string {
  const cleaned = base.trim().replace(/\/+$/, "")
  if (cleaned.startsWith("https://")) return `wss://${cleaned.slice("https://".length)}`
  if (cleaned.startsWith("http://")) return `ws://${cleaned.slice("http://".length)}`
  if (cleaned.startsWith("wss://") || cleaned.startsWith("ws://")) return cleaned
  return `wss://${cleaned}`
}

/** Resolve absolute WS origin (no path) for Pipecat. */
export function resolvePipecatWsOrigin(status?: VoiceStatus | null): string {
  const env =
    (typeof process !== "undefined" &&
      (process.env.NEXT_PUBLIC_VOICE_WS_BASE || process.env.NEXT_PUBLIC_BACKEND_WS_URL || "").trim()) ||
    ""
  if (env) return httpBaseToWs(env)
  const hint = (status?.pipecat_ws_hint || "").trim()
  if (hint) return httpBaseToWs(hint)
  return httpBaseToWs(PRODUCTION_API_URL)
}

export function shouldUsePipecatVoice(status: VoiceStatus | null | undefined): boolean {
  if (!status) return false
  if (status.pipecat_enabled === false) return false
  if (status.pipecat_ws_clients_accepted === false) return false
  return Boolean(status.pipecat_enabled && status.pipecat_available !== false)
}

export async function buildPipecatVoiceWsUrl(options: {
  status?: VoiceStatus | null
  agentId?: string | null
  conversationId?: string | null
  voice?: string | null
  path?: string
}): Promise<{ url: string; token: string; orgId: string } | { error: string }> {
  const token = await getAccessToken()
  if (!token) return { error: "Not signed in" }
  const orgId = getSelectedOrgFromStorage()?.id || ""
  if (!orgId) return { error: "Organization required" }

  const origin = resolvePipecatWsOrigin(options.status)
  const path = (options.path || options.status?.pipecat_ws_path || "/api/voice/pipecat/ws").trim()
  const params = new URLSearchParams()
  params.set("access_token", token)
  params.set("org_id", orgId)
  if (options.agentId) params.set("agent_id", options.agentId)
  if (options.conversationId) params.set("conversation_id", options.conversationId)
  if (options.voice) params.set("voice", options.voice)

  const slashPath = path.startsWith("/") ? path : `/${path}`
  return {
    url: `${origin}${slashPath}?${params.toString()}`,
    token,
    orgId,
  }
}

export function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength)
  let binary = ""
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

function base64ToBytes(b64: string): Uint8Array {
  const raw = atob(b64)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/** Little-endian PCM16 from bytes; DataView so the host's byte order never matters. */
function bytesToPcm16(bytes: Uint8Array, start: number, samples: number): Int16Array {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const out = new Int16Array(samples)
  for (let i = 0; i < samples; i++) out[i] = view.getInt16(start + i * 2, true)
  return out
}

/** Decode one self-contained PCM16 message. A trailing odd byte is dropped. */
export function base64ToPcm16(b64: string): Int16Array {
  const bytes = base64ToBytes(b64)
  return bytesToPcm16(bytes, 0, Math.floor(bytes.byteLength / 2))
}

export type Pcm16StreamDecoder = {
  /** Decode the next message of a stream; a split sample is completed by the next call. */
  decode: (b64: string) => Int16Array
  reset: () => void
}

/**
 * Decoder for a stream of PCM16 messages. Decoding each message on its own
 * drops an odd trailing byte, which shifts every later sample by one byte:
 * full-scale noise until the next odd message. This carries the byte over.
 */
export function createPcm16StreamDecoder(): Pcm16StreamDecoder {
  let carry: number | null = null
  return {
    decode(b64) {
      let bytes = base64ToBytes(b64)
      if (carry !== null) {
        const joined = new Uint8Array(bytes.length + 1)
        joined[0] = carry
        joined.set(bytes, 1)
        bytes = joined
        carry = null
      }
      const samples = Math.floor(bytes.length / 2)
      if (bytes.length % 2 === 1) carry = bytes[bytes.length - 1] ?? null
      return bytesToPcm16(bytes, 0, samples)
    },
    reset() {
      carry = null
    },
  }
}

export type PcmEnergy = {
  peak: number
  rms: number
  audible: boolean
}

/**
 * Browser-side guard against "audio frames arrived" being mistaken for
 * "audible speech arrived". Providers can emit non-empty leading-silence or
 * zeroed PCM frames. Those must not disarm the no-audio recovery watchdog.
 *
 * Thresholds are intentionally low relative to int16 full scale: enough to
 * ignore digital silence / tiny transport noise without requiring normal
 * speech loudness. A later real speech frame clears the watchdog immediately.
 */
export function inspectPcm16Energy(pcm: Int16Array): PcmEnergy {
  if (!pcm.length) return { peak: 0, rms: 0, audible: false }

  let peak = 0
  let sumSquares = 0
  for (let i = 0; i < pcm.length; i++) {
    const sample = Math.abs(pcm[i] ?? 0)
    if (sample > peak) peak = sample
    sumSquares += sample * sample
  }
  const rms = Math.sqrt(sumSquares / pcm.length)
  return {
    peak,
    rms,
    audible: peak >= 96 && rms >= 24,
  }
}

export function encodePipecatAudioMessage(
  pcm: Int16Array,
  sampleRate = 16000,
  numChannels = 1,
): string {
  return JSON.stringify({
    type: "audio",
    pcm16_b64: pcm16ToBase64(pcm),
    sample_rate: sampleRate,
    num_channels: numChannels,
  } satisfies PipecatOutboundAudio)
}

export function encodePipecatInterrupt(options?: { playbackOffsetMs?: number | null }): string {
  const payload: { type: "interrupt"; playback_offset_ms?: number } = { type: "interrupt" }
  const offset = options?.playbackOffsetMs
  if (typeof offset === "number" && Number.isFinite(offset) && offset >= 0) {
    payload.playback_offset_ms = offset
  }
  return JSON.stringify(payload)
}
