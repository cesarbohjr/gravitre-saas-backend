/**
 * Tier 1 paid-provider voice client (ElevenLabs TTS / Deepgram STT via backend).
 * Falls back to browser Web Speech when providers are not configured.
 */

import { apiFetch } from "@/lib/fetcher"
import { parseTtsErrorBody, type TtsSynthesizeError } from "@/lib/tts-error"

export type { TtsSynthesizeError }
export { parseTtsErrorBody }

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

/** QA-only header — honored only when backend unified_turn_qa_hooks_enabled. */
export const QA_FORCE_VOICE_ERROR_HEADER = "X-Gravitre-QA-Force-Voice-Error"

export type TtsSynthesizeOk = {
  ok: true
  blob: Blob
  latencyMs: number | null
}

export type TtsSynthesizeResult = TtsSynthesizeOk | TtsSynthesizeError

export type SynthesizeOptions = {
  voice?: string
  agentId?: string
  /** QA-only: force billing | service_failure | auth | rate_limit */
  qaForceError?: string | null
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

/**
 * Same `/api/voice/tts` path used by main-chat Read aloud.
 * Returns structured ok/error so 402/billing is never silently swallowed.
 */
export async function synthesizeViaElevenLabsDetailed(
  text: string,
  options?: SynthesizeOptions,
): Promise<TtsSynthesizeResult> {
  const status = await getVoiceStatus()
  if (!status?.tts_enabled) {
    return {
      ok: false,
      status: 0,
      errorClass: null,
      billingIssue: false,
      detail: "TTS provider not configured",
      disabled: true,
    }
  }
  const headers: Record<string, string> = {
    "content-type": "application/json",
    accept: "audio/mpeg",
  }
  const qa = (options?.qaForceError || "").trim()
  if (qa) headers[QA_FORCE_VOICE_ERROR_HEADER] = qa

  const res = await apiFetch("/api/voice/tts", {
    method: "POST",
    headers,
    body: JSON.stringify({
      text,
      voice: options?.voice || status.default_voice || "rachel",
      ...(options?.agentId ? { agent_id: options.agentId } : {}),
    }),
    timeoutMs: 45_000,
  })
  if (!res.ok) {
    let parsed: unknown = null
    try {
      parsed = await res.json()
    } catch {
      parsed = null
    }
    return parseTtsErrorBody(parsed, res.status)
  }
  const blob = await res.blob()
  const latencyRaw = res.headers.get("x-voice-latency-ms")
  const latencyMs = latencyRaw ? Number(latencyRaw) : null
  return { ok: true, blob, latencyMs: Number.isFinite(latencyMs) ? latencyMs : null }
}

/** Compatibility wrapper for Read aloud — success blob or null (legacy callers). */
export async function synthesizeViaElevenLabs(
  text: string,
  voice?: string,
): Promise<{ blob: Blob; latencyMs: number | null } | null> {
  const result = await synthesizeViaElevenLabsDetailed(text, { voice })
  if (result.ok) return { blob: result.blob, latencyMs: result.latencyMs }
  return null
}

export type SttTranscribeOk = {
  ok: true
  transcript: string
  latencyMs: number | null
}

export type SttTranscribeError = {
  ok: false
  status: number
  detail: string
}

export type SttTranscribeResult = SttTranscribeOk | SttTranscribeError

/** Same Deepgram path as agent voice STT — structured errors for Dictate. */
export async function transcribeViaDeepgramDetailed(blob: Blob): Promise<SttTranscribeResult> {
  const status = await getVoiceStatus()
  if (!status?.stt_enabled) {
    return { ok: false, status: 0, detail: "Speech-to-text is not configured for this environment." }
  }
  const form = new FormData()
  const mime = blob.type || "audio/webm"
  const filename = mime.includes("wav") ? "audio.wav" : "audio.webm"
  form.append("file", new File([blob], filename, { type: mime }))
  const res = await apiFetch("/api/voice/stt", {
    method: "POST",
    body: form,
    timeoutMs: 45_000,
  })
  let payload: Record<string, unknown> = {}
  try {
    payload = (await res.json()) as Record<string, unknown>
  } catch {
    payload = {}
  }
  if (!res.ok) {
    const detail =
      (typeof payload.error === "string" && payload.error) ||
      (typeof payload.detail === "string" && payload.detail) ||
      (typeof (payload.detail as { error?: string } | undefined)?.error === "string"
        ? (payload.detail as { error: string }).error
        : null) ||
      `Transcription failed (HTTP ${res.status})`
    return { ok: false, status: res.status, detail: String(detail) }
  }
  return {
    ok: true,
    transcript: String(payload.transcript || "").trim(),
    latencyMs: typeof payload.latency_ms === "number" ? payload.latency_ms : null,
  }
}

export async function transcribeViaDeepgram(blob: Blob): Promise<{
  transcript: string
  latencyMs: number | null
} | null> {
  const result = await transcribeViaDeepgramDetailed(blob)
  if (!result.ok) return null
  return { transcript: result.transcript, latencyMs: result.latencyMs }
}
