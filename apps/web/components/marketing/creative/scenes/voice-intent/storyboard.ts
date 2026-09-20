/**
 * Phase 9 — Voice Intent Field storyboard (illustrative, deterministic).
 * Waveform → structure → intent → context → action → response (no Siri orb).
 */

export const ILLUSTRATIVE_CONTEXT =
  "Voice enters the same brain as chat — structure the utterance, resolve intent and context, then act and respond."

export const VOICE_STAGES = [
  { id: "waveform", label: "Waveform" },
  { id: "structure", label: "Structure" },
  { id: "intent", label: "Intent" },
  { id: "context", label: "Context" },
  { id: "action", label: "Action" },
  { id: "response", label: "Response" },
] as const

export type VoicePhase =
  | "quiet"
  | "waveform"
  | "structure"
  | "intent"
  | "context"
  | "action"
  | "response"
  | "honest"

export const PHASE_ORDER: VoicePhase[] = [
  "quiet",
  "waveform",
  "structure",
  "intent",
  "context",
  "action",
  "response",
  "honest",
]

export const PHASE_CAPTION: Record<VoicePhase, string> = {
  quiet: "Voice at rest — no listening orb.",
  waveform: "Audio arrives as a waveform — structure first, not a glowing sphere.",
  structure: "Utterance becomes semantic structure (tokens / phrases).",
  intent: "Intent resolves against what you asked for.",
  context: "Org context attaches — memory and permissions, not a free-floating assistant.",
  action: "Action routes through the same governed path as chat.",
  response: "Spoken response returns — still the same brain.",
  honest: "Illustrative path only — not proven duplex parity.",
}

export const STRUCTURE_CHIPS = ["tokens", "phrases", "entities"] as const

export function nextPhase(phase: VoicePhase): VoicePhase {
  const i = PHASE_ORDER.indexOf(phase)
  return PHASE_ORDER[(i + 1) % PHASE_ORDER.length] ?? "quiet"
}

export function isVoicePhase(value: string | null | undefined): value is VoicePhase {
  if (!value) return false
  return (PHASE_ORDER as string[]).includes(value)
}

export function parseVoiceStateParam(
  raw: string | null | undefined,
  opts?: { hostname?: string | null },
): VoicePhase | null {
  if (!isVoicePhase(raw)) return null
  const host = (opts?.hostname ?? "").toLowerCase()
  const local =
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".localhost") ||
    process.env.NODE_ENV === "development"
  return local ? raw : null
}

export function activeStageIds(phase: VoicePhase): string[] {
  switch (phase) {
    case "quiet":
      return []
    case "waveform":
      return ["waveform"]
    case "structure":
      return ["waveform", "structure"]
    case "intent":
      return ["waveform", "structure", "intent"]
    case "context":
      return ["waveform", "structure", "intent", "context"]
    case "action":
      return ["waveform", "structure", "intent", "context", "action"]
    case "response":
    case "honest":
      return ["waveform", "structure", "intent", "context", "action", "response"]
    default:
      return []
  }
}

export function showWaveform(phase: VoicePhase): boolean {
  return phase !== "quiet"
}

export function showStructure(phase: VoicePhase): boolean {
  return ["structure", "intent", "context", "action", "response", "honest"].includes(phase)
}

export function showResponse(phase: VoicePhase): boolean {
  return phase === "response" || phase === "honest"
}

/** Same turn id continues through action → response (no restart). */
export const VOICE_TURN_PATH_ID = "path-voice-turn"
