import {
  CHAT_PERSONA_OPTIONS,
  DEFAULT_CHAT_PERSONA_KEY,
  resolveChatPersonaLabel,
} from "@/lib/chat-personas"

export const DEFAULT_AGENT_RESPONSE_STYLE = DEFAULT_CHAT_PERSONA_KEY

export function isAgentResponseStyleKey(value: string | null | undefined): boolean {
  const key = String(value || "").trim()
  return CHAT_PERSONA_OPTIONS.some((option) => option.key === key)
}

export function normalizeAgentResponseStyle(value: string | null | undefined): string {
  const key = String(value || "").trim()
  return isAgentResponseStyleKey(key) ? key : DEFAULT_AGENT_RESPONSE_STYLE
}

export function readResponseStyleFromConfig(config: unknown): string {
  if (!config || typeof config !== "object") return DEFAULT_AGENT_RESPONSE_STYLE
  const record = config as Record<string, unknown>
  const raw = record.response_style ?? record.responseStyle ?? record.preferred_persona
  return normalizeAgentResponseStyle(typeof raw === "string" ? raw : null)
}

export function responseStyleLabel(key: string | null | undefined): string {
  return resolveChatPersonaLabel(normalizeAgentResponseStyle(key))
}

export { CHAT_PERSONA_OPTIONS as AGENT_RESPONSE_STYLE_OPTIONS }
