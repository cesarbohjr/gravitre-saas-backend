/**
 * Tier 1 paid-provider voice client (ElevenLabs TTS / Deepgram STT via backend).
 * Falls back to browser Web Speech when providers are not configured.
 */

import { apiFetch } from "@/lib/fetcher"

export type VoiceStatus = {
  tts_enabled: boolean
  stt_enabled: boolean
  default_voice?: string
  voices?: Array<{ key: string; id: string; label: string; description: string }>
  write_confirm_policy?: string
  architecture?: string
}

let cachedStatus: VoiceStatus | null = null
let cachedAt = 0

export type VoiceStatusResult = {
  status: VoiceStatus | null
  /** HTTP status from /api/voice/status when the request completed. */
  httpStatus?: number
  blocked?: boolean
  reason?: string
}

export async function getVoiceStatus(force = false): Promise<VoiceStatus | null> {
  const result = await getVoiceStatusDetailed(force)
  return result.status
}

export async function getVoiceStatusDetailed(force = false): Promise<VoiceStatusResult> {
  const now = Date.now()
  if (!force && cachedStatus && now - cachedAt < 60_000) {
    return { status: cachedStatus, blocked: false }
  }
  try {
    const res = await apiFetch("/api/voice/status", { timeoutMs: 8_000 })
    if (!res.ok) {
      if (res.status === 403) {
        cachedStatus = null
        cachedAt = 0
        return {
          status: null,
          httpStatus: 403,
          blocked: true,
          reason: "Voice is turned off for this organization or not available for your seat.",
        }
      }
      return { status: force ? null : cachedStatus, httpStatus: res.status, blocked: false }
    }
    const data = (await res.json()) as VoiceStatus
    cachedStatus = data
    cachedAt = now
    return { status: data, httpStatus: 200, blocked: false }
  } catch {
    return { status: force ? null : cachedStatus, blocked: false }
  }
}

export async function synthesizeViaElevenLabs(
  text: string,
  voice?: string,
): Promise<{ blob: Blob; latencyMs: number | null } | null> {
  const status = await getVoiceStatus()
  if (!status?.tts_enabled) return null
  const res = await apiFetch("/api/voice/tts", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({ text, voice: voice || status.default_voice || "rachel" }),
    timeoutMs: 45_000,
  })
  if (!res.ok) return null
  const blob = await res.blob()
  const latencyRaw = res.headers.get("x-voice-latency-ms")
  const latencyMs = latencyRaw ? Number(latencyRaw) : null
  return { blob, latencyMs: Number.isFinite(latencyMs) ? latencyMs : null }
}

export async function transcribeViaDeepgram(blob: Blob): Promise<{
  transcript: string
  latencyMs: number | null
} | null> {
  const status = await getVoiceStatus()
  if (!status?.stt_enabled) return null
  const form = new FormData()
  form.append("file", blob, "audio.webm")
  const res = await apiFetch("/api/voice/stt", {
    method: "POST",
    body: form,
    timeoutMs: 45_000,
  })
  if (!res.ok) return null
  const data = (await res.json()) as { transcript?: string; latency_ms?: number }
  return {
    transcript: String(data.transcript || "").trim(),
    latencyMs: typeof data.latency_ms === "number" ? data.latency_ms : null,
  }
}
