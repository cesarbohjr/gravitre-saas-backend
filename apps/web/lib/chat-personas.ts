export type ChatPersonaOption = {
  key: string
  label: string
  tone?: string | null
  verbosity?: string | null
  isOrgDefault?: boolean
}

export const CHAT_PERSONA_OPTIONS: ChatPersonaOption[] = [
  { key: "friendly_assistant", label: "Friendly Assistant", tone: "warm", verbosity: "moderate" },
  { key: "executive_strategist", label: "Executive Strategist", tone: "authoritative", verbosity: "concise" },
  { key: "sales_advisor", label: "Sales Advisor", tone: "confident", verbosity: "moderate" },
  { key: "marketing_operator", label: "Marketing Operator", tone: "energetic", verbosity: "moderate" },
  { key: "operations_analyst", label: "Operations Analyst", tone: "precise", verbosity: "detailed" },
  { key: "support_specialist", label: "Support Specialist", tone: "empathetic", verbosity: "moderate" },
  { key: "finance_analyst", label: "Finance Analyst", tone: "analytical", verbosity: "detailed" },
  { key: "engineering_copilot", label: "Engineering Copilot", tone: "technical", verbosity: "detailed" },
  { key: "deep_research_analyst", label: "Deep Research Analyst", tone: "scholarly", verbosity: "detailed" },
]

export const DEFAULT_CHAT_PERSONA_KEY = "friendly_assistant"

export function resolveChatPersonaLabel(key: string | null | undefined, options = CHAT_PERSONA_OPTIONS): string {
  const normalized = (key || DEFAULT_CHAT_PERSONA_KEY).trim()
  return options.find((option) => option.key === normalized)?.label ?? "Friendly Assistant"
}

export function normalizeChatPersonaOptions(
  personas: Array<{
    persona_key?: string
    label?: string
    tone?: string | null
    verbosity?: string | null
    is_org_default?: boolean
  }> | undefined,
): ChatPersonaOption[] {
  if (!personas?.length) return CHAT_PERSONA_OPTIONS
  return personas
    .map((persona) => ({
      key: String(persona.persona_key || "").trim(),
      label: String(persona.label || persona.persona_key || "").trim(),
      tone: persona.tone ?? null,
      verbosity: persona.verbosity ?? null,
      isOrgDefault: Boolean(persona.is_org_default),
    }))
    .filter((persona) => persona.key.length > 0)
}
