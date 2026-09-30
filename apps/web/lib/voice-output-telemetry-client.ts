import { apiFetch } from "@/lib/fetcher"

export type VoiceOutputDiagnosticEvent =
  | "audio_missing"
  | "audio_silent"
  | "output_unavailable"
  | "playback_blocked"
  | "playback_started"
  | "playback_recovered"

export type VoiceOutputDiagnosticsPayload = {
  session_id?: string | null
  turn_id?: string | null
  orchestration?: "pipecat" | "http"
  event: VoiceOutputDiagnosticEvent
  audio_context_state?: string | null
  pcm_frames_received?: number
  audible_pcm_frames?: number
  max_pcm_peak?: number
  fallback_triggered?: boolean
  playback_blocked?: boolean
  browser_audio_playback_started?: boolean
}

/**
 * Best-effort browser output telemetry. No audio samples, transcript text, or
 * credentials are sent. Failures never interrupt the voice session.
 */
export async function postVoiceOutputDiagnostics(
  body: VoiceOutputDiagnosticsPayload,
): Promise<boolean> {
  try {
    const res = await apiFetch("/api/voice/output-diagnostics", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: 6_000,
    })
    if (!res.ok) return false
    const data = (await res.json()) as { status?: string }
    return data.status === "ok"
  } catch {
    return false
  }
}
