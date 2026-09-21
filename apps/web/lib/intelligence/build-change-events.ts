import type { IntelligencePageContextResponse } from "@/lib/api"

export type IntelligenceChangeEvent = {
  id: string
  kind: string
  title: string
  at: string
  focusNodeIds: string[]
  askPrompt: string
}

/** Derive I2 change events from snapshot learnings/predictions/outcomes — no browser-session fabrication. */
export function buildChangeEvents(
  pageContext?: IntelligencePageContextResponse | null,
): IntelligenceChangeEvent[] {
  if (!pageContext?.snapshot) return []
  const events: IntelligenceChangeEvent[] = []
  const snap = pageContext.snapshot

  for (const learning of snap.learnings ?? []) {
    const id = String(learning.id ?? "")
    if (!id) continue
    events.push({
      id: `learning:${id}`,
      kind: "learned",
      title: String(learning.businessStatement ?? "Learning").slice(0, 120),
      at: String(learning.learnedAt ?? ""),
      focusNodeIds: [`learning:${id}`],
      askPrompt: `Explain this learning: ${String(learning.businessStatement ?? "").slice(0, 160)}`,
    })
  }

  for (const prediction of snap.predictions ?? []) {
    const id = String(prediction.id ?? "")
    if (!id) continue
    events.push({
      id: `prediction:${id}`,
      kind: "prediction",
      title: String(prediction.businessStatement ?? "Prediction").slice(0, 120),
      at: "",
      focusNodeIds: [`prediction:${id}`],
      askPrompt: `Why is this prediction active: ${String(prediction.businessStatement ?? "").slice(0, 160)}`,
    })
  }

  for (const outcome of snap.outcomes ?? []) {
    const id = String(outcome.id ?? "")
    const event = String(outcome.event ?? "outcome")
    if (!id) continue
    const entityId = outcome.entityId ? String(outcome.entityId) : null
    const entityType = outcome.entityType ? String(outcome.entityType) : "entity"
    events.push({
      id: `outcome:${id}`,
      kind: "changed",
      title: event.replace(/_/g, " "),
      at: String(outcome.createdAt ?? ""),
      focusNodeIds: entityId ? [`kg:${entityType}:${entityId}`] : [],
      askPrompt: `What changed around outcome ${event}?`,
    })
  }

  return events.slice(0, 24)
}
