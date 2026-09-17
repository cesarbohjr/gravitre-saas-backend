/**
 * Customer-facing context lines for the canonical AI workspace.
 * Built from provider state — Phase 2 chrome must not reconstruct context.
 */

export type GravitreAiContextLabelInput = {
  agentName?: string | null
  selectedKind?: string | null
  selectedLabel?: string | null
}

export type GravitreAiContextLabel = {
  agentLine: string | null
  selectionLine: string | null
}

function titleKind(kind: string): string {
  const trimmed = kind.trim()
  if (!trimmed) return "object"
  return trimmed.replace(/[_-]+/g, " ")
}

export function formatGravitreAiContextLabel(
  input: GravitreAiContextLabelInput,
): GravitreAiContextLabel {
  const agentName = input.agentName?.trim() || null
  const selectedLabel = input.selectedLabel?.trim() || null
  const selectedKind = input.selectedKind?.trim() || null

  return {
    agentLine: agentName ? `Talking with ${agentName}` : null,
    selectionLine:
      selectedLabel && selectedKind
        ? `Using ${titleKind(selectedKind)}: ${selectedLabel}`
        : selectedLabel
          ? `Using ${selectedLabel}`
          : null,
  }
}

export function gravitreAiContextHasVisibleState(label: GravitreAiContextLabel): boolean {
  return Boolean(label.agentLine || label.selectionLine)
}

/** Helper subtitle: live voice/work presence wins over object/agent context. */
export function gravitreHelperStatusCopy(
  presence: string,
  presenceLabel: string,
  context: GravitreAiContextLabel,
): string {
  const live =
    presence === "listening" ||
    presence === "thinking" ||
    presence === "executing" ||
    presence === "needs_approval" ||
    presence === "error"
  if (live) return presenceLabel
  return context.agentLine || context.selectionLine || presenceLabel
}
