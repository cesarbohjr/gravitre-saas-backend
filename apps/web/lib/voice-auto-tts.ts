/**
 * When the workspace may read an assistant reply aloud on its own.
 *
 * Arming Voice used to speak the conversation's last assistant message: the
 * auto-TTS effect ran as soon as modality flipped to "voice", before the live
 * session was up, and nothing had ever been marked spoken. Opening Talk on a
 * conversation whose last text reply was a HubSpot count announced that count
 * unprompted (and the mic could then pick the playback up as a user turn).
 *
 * The rule now: a reply is spoken only when it answers something the user asked
 * while Voice was armed. A claim records that ask, so arming Voice, switching
 * conversations or hydrating history never speaks anything.
 */

export type VoiceReplyClaim =
  /** A chat turn sent while Voice was armed: speak the first reply newer than this one. */
  | { kind: "after"; afterAssistantId: string | null }
  /** A live-voice turn whose audio never played: speak exactly this message. */
  | { kind: "message"; messageId: string }

type RoleMessage = { id: string; role: string }

export function lastAssistantMessageId(messages: readonly RoleMessage[]): string | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i]?.role === "assistant") return messages[i]!.id
  }
  return null
}

export function shouldAutoSpeakReply(options: {
  lastAssistantId: string | null
  lastSpokenId: string | null
  claim: VoiceReplyClaim | null
}): boolean {
  const { lastAssistantId, lastSpokenId, claim } = options
  if (!claim || !lastAssistantId) return false
  if (lastSpokenId === lastAssistantId) return false
  if (claim.kind === "message") return claim.messageId === lastAssistantId
  return lastAssistantId !== claim.afterAssistantId
}

/**
 * Keep a claim tied to the conversation it was made in.
 *
 * A claim made on a brand-new chat has no conversation yet (`owner` null) and
 * adopts the first id the chat gets. Any later switch to a different
 * conversation drops the claim, so an "after" claim can never read another
 * thread's last reply aloud.
 */
export function reconcileClaimOnConversationChange(options: {
  claim: VoiceReplyClaim | null
  owner: string | null
  next: string | null
}): { claim: VoiceReplyClaim | null; owner: string | null } {
  const { claim, owner, next } = options
  if (!claim) return { claim: null, owner: null }
  if (owner === null) return { claim, owner: next }
  if (owner !== next) return { claim: null, owner: null }
  return { claim, owner }
}
