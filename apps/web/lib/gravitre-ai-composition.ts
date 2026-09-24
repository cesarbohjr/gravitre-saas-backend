/**
 * AI workspace composition — Conversation / Work / Split (3.0 Plus Slice 1).
 *
 * Presentation only: chooses which of the existing panes (transcript, work
 * canvas) are visible. It never creates or hides runtime state.
 *
 * Honesty rules:
 * - Work and Split need a real work artifact; without one only Conversation is offered.
 * - Work hides the transcript, and the transcript holds the approval card, so Work
 *   is unavailable while an approval is visible (Split is used instead).
 */

export const AI_WORKSPACE_COMPOSITIONS = ["conversation", "work", "split"] as const
export type AiWorkspaceComposition = (typeof AI_WORKSPACE_COMPOSITIONS)[number]

export const GRAVITRE_AI_COMPOSITION_STORAGE_KEY = "gravitre.ai.composition.v1"
export const GRAVITRE_AI_COMPOSITION_EVENT = "gravitre:ai-composition"

export function isAiWorkspaceComposition(value: unknown): value is AiWorkspaceComposition {
  return typeof value === "string" && (AI_WORKSPACE_COMPOSITIONS as readonly string[]).includes(value)
}

export interface ResolvedComposition {
  composition: AiWorkspaceComposition
  available: readonly AiWorkspaceComposition[]
  /** Why a requested composition was not honoured, for the switch's description. */
  reason: "no-work" | "approval-visible" | null
}

export function resolveWorkspaceComposition(args: {
  preferred: AiWorkspaceComposition | null
  hasWork: boolean
  approvalVisible: boolean
}): ResolvedComposition {
  if (!args.hasWork) {
    return { composition: "conversation", available: ["conversation"], reason: args.preferred && args.preferred !== "conversation" ? "no-work" : null }
  }
  if (args.approvalVisible) {
    const composition = args.preferred === "conversation" ? "conversation" : "split"
    return {
      composition,
      available: ["conversation", "split"],
      reason: args.preferred === "work" ? "approval-visible" : null,
    }
  }
  return { composition: args.preferred ?? "split", available: AI_WORKSPACE_COMPOSITIONS, reason: null }
}

export function readCompositionPreference(
  storage: Pick<Storage, "getItem"> | null | undefined = typeof window !== "undefined" ? window.localStorage : null,
): AiWorkspaceComposition | null {
  if (!storage) return null
  try {
    const raw = storage.getItem(GRAVITRE_AI_COMPOSITION_STORAGE_KEY)
    return isAiWorkspaceComposition(raw) ? raw : null
  } catch {
    return null
  }
}

export function writeCompositionPreference(
  composition: AiWorkspaceComposition,
  storage: Pick<Storage, "setItem"> | null | undefined = typeof window !== "undefined" ? window.localStorage : null,
): void {
  if (!storage) return
  try {
    storage.setItem(GRAVITRE_AI_COMPOSITION_STORAGE_KEY, composition)
  } catch {
    // Best-effort preference.
  }
  if (typeof window !== "undefined") window.dispatchEvent(new Event(GRAVITRE_AI_COMPOSITION_EVENT))
}

export function subscribeCompositionPreference(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => {}
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === GRAVITRE_AI_COMPOSITION_STORAGE_KEY) onChange()
  }
  window.addEventListener("storage", onStorage)
  window.addEventListener(GRAVITRE_AI_COMPOSITION_EVENT, onChange)
  return () => {
    window.removeEventListener("storage", onStorage)
    window.removeEventListener(GRAVITRE_AI_COMPOSITION_EVENT, onChange)
  }
}
