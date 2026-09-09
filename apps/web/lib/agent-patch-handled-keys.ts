/** Keys handled by Next.js PATCH /api/agents/[id] (Supabase path, not FastAPI proxy). */
export const AGENT_PATCH_HANDLED_KEYS = [
  "name",
  "icon",
  "avatarColor",
  "avatar_color",
  "avatarUrl",
  "avatar_url",
  "personality",
  "description",
  "role",
  "department",
  "model",
  "voiceProfile",
  "voice_profile",
  "capabilities",
  "systems",
  "permissions",
  "guardrails",
  "responseStyle",
  "response_style",
  "referenceFolders",
  "reference_folders",
  "knowledgePacks",
  "knowledge_packs",
] as const

export function agentPatchBodyIsHandled(body: Record<string, unknown>, snakeBody: Record<string, unknown>): boolean {
  return AGENT_PATCH_HANDLED_KEYS.some((key) => key in body || key in snakeBody)
}
