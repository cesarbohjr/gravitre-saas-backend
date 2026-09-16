/**
 * I9 — Report templates compose existing intelligence surfaces.
 * No invented metrics; templates only name which real sources to show.
 */
export const REPORT_TEMPLATES = [
  {
    id: "business",
    label: "Business",
    description: "Measured outcomes and attribution from the IMPROVES snapshot.",
  },
  {
    id: "agent",
    label: "Agent",
    description: "Agent contribution from recorded ROI — estimates stay labeled.",
  },
  {
    id: "prediction",
    label: "Prediction",
    description: "Forward-looking predictions from the canonical snapshot.",
  },
  {
    id: "governance",
    label: "Governance",
    description: "Quality flags, approvals waiting, and evidence gaps.",
  },
] as const

export type ReportTemplateId = (typeof REPORT_TEMPLATES)[number]["id"]

export type SavedIntelligenceView = {
  id: string
  label: string
  templateId: ReportTemplateId
  periodDays: 7 | 30 | 90
  savedAt: string
}

const STORAGE_PREFIX = "gravitre.intelligence.saved-views.v1."

function storageKey(orgId: string): string {
  return `${STORAGE_PREFIX}${orgId}`
}

export function readSavedIntelligenceViews(orgId: string | null | undefined): SavedIntelligenceView[] {
  if (!orgId || typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(storageKey(orgId))
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isSavedView)
  } catch {
    return []
  }
}

export function writeSavedIntelligenceViews(
  orgId: string,
  views: SavedIntelligenceView[],
): SavedIntelligenceView[] {
  if (typeof window === "undefined") return views
  window.localStorage.setItem(storageKey(orgId), JSON.stringify(views))
  return views
}

export function saveIntelligenceView(
  orgId: string,
  input: Omit<SavedIntelligenceView, "id" | "savedAt"> & { id?: string },
): SavedIntelligenceView[] {
  const current = readSavedIntelligenceViews(orgId)
  const nextView: SavedIntelligenceView = {
    id: input.id ?? `view-${Date.now()}`,
    label: input.label.trim() || REPORT_TEMPLATES.find((t) => t.id === input.templateId)?.label || "Saved view",
    templateId: input.templateId,
    periodDays: input.periodDays,
    savedAt: new Date().toISOString(),
  }
  const next = [nextView, ...current.filter((row) => row.id !== nextView.id)].slice(0, 20)
  return writeSavedIntelligenceViews(orgId, next)
}

export function deleteSavedIntelligenceView(orgId: string, id: string): SavedIntelligenceView[] {
  const next = readSavedIntelligenceViews(orgId).filter((row) => row.id !== id)
  return writeSavedIntelligenceViews(orgId, next)
}

function isSavedView(value: unknown): value is SavedIntelligenceView {
  if (!value || typeof value !== "object") return false
  const row = value as Record<string, unknown>
  const templateOk = REPORT_TEMPLATES.some((t) => t.id === row.templateId)
  const period = row.periodDays
  return (
    typeof row.id === "string" &&
    typeof row.label === "string" &&
    templateOk &&
    (period === 7 || period === 30 || period === 90) &&
    typeof row.savedAt === "string"
  )
}
