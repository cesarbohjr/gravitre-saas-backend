/**
 * POST mic level diagnostics to backend (Voice 3.0 Phase 1 — no raw audio).
 */

import { apiFetch } from "@/lib/fetcher"
import type { MicEffectiveSettings, MicLevelSnapshot } from "@/lib/voice-mic-capture"

export type MicDiagnosticsPayload = {
  session_id?: string
  orchestration?: "pipecat" | "http"
  mic_profile?: string
  device_label?: string
  effective_settings?: MicEffectiveSettings
  /** Levels may be absent at session_start/end before the first capture tick. */
  metrics: Partial<MicLevelSnapshot> & Record<string, unknown>
  event?: "session_start" | "periodic" | "session_end" | "echo_test"
}

export async function postMicDiagnostics(body: MicDiagnosticsPayload): Promise<boolean> {
  try {
    const res = await apiFetch("/api/voice/mic-diagnostics", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: 6_000,
    })
    if (!res.ok) return false
    const data = (await res.json()) as { status?: string }
    return data.status === "ok" || data.status === "disabled"
  } catch {
    return false
  }
}
