import type { AgentVoiceProfile } from "@/types/api"

// No local provider mapping: an explicit ID is authoritative but opaque.
// A persisted alias or descriptor is not verified identity metadata.
export function effectiveVoiceLabel(profile?: AgentVoiceProfile): string {
  if (profile?.voice_source === "custom_voice_v3") return "Custom voice"
  if (profile?.voice_id?.trim()) return "Assigned voice"
  if (profile?.voice_key?.trim()) return "Configured voice"
  return "Default spoken voice"
}
