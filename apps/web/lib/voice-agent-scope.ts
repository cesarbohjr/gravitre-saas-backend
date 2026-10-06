/**
 * Which agent a live voice session (duplex WS / HTTP TTS) runs as.
 *
 * - On an agent-scoped chat (e.g. /agents/[id]/chat) voice always runs as that
 *   agent, so its response style, skills, knowledge and safety rules apply to
 *   spoken turns too. Agents without a configured voice profile still work: the
 *   backend falls back to the default voice.
 * - Unscoped, the voice picker's pick (already validated as voice-ready) is used;
 *   no pick means the default assistant voice.
 */
export function resolveVoiceAgentId(input: {
  scopedAgentId?: string | null
  pickedAgentId?: string | null
}): string | undefined {
  const scoped = String(input.scopedAgentId ?? "").trim()
  if (scoped) return scoped
  const picked = String(input.pickedAgentId ?? "").trim()
  return picked || undefined
}

/** The voice picker only makes sense when no agent scope fixes the voice agent. */
export function showVoiceAgentPicker(scopedAgentId?: string | null): boolean {
  return !String(scopedAgentId ?? "").trim()
}
