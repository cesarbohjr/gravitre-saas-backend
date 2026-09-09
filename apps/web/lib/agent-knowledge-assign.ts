export type PackAssignInput = {
  id: string
  name: string
  department?: string
}

export function buildPackAssignmentPayload(pack: PackAssignInput) {
  return {
    sourceType: "knowledge_pack" as const,
    sourceId: pack.id,
    label: pack.name,
    department: pack.department,
    enabled: true,
    metadata: { fabric_pack: true },
  }
}

export function buildOrgSourceAssignmentPayload(source: { id: string; name: string }) {
  return {
    sourceType: "rag_source" as const,
    sourceId: source.id,
    label: source.name,
    enabled: true,
    metadata: { org_rag_source: true },
  }
}

/** Customer-facing error when atomic assign fails (never generic save toast). */
function readErrorStatus(error: unknown): number | undefined {
  if (error && typeof error === "object" && "status" in error) {
    const status = Number((error as { status?: unknown }).status)
    return Number.isFinite(status) ? status : undefined
  }
  return undefined
}

export function formatKnowledgeAssignError(error: unknown, label: string): string {
  const status = readErrorStatus(error)
  if (status === 403) {
    return `${label} couldn't be assigned. Your organization doesn't have permission to change agent knowledge.`
  }
  if (status === 409) {
    return `${label} is already assigned to this agent.`
  }
  if (status === 422) {
    return `${label} couldn't be assigned. The source type isn't supported.`
  }
  if (error instanceof Error && error.message && status) {
    return `${label} couldn't be assigned. ${error.message}`
  }
  if (error instanceof Error && error.message) {
    return `${label} couldn't be assigned. ${error.message}`
  }
  return `${label} couldn't be assigned. Your previous configuration is unchanged.`
}

export function formatKnowledgeRemoveError(error: unknown, label: string): string {
  if (error instanceof Error && error.message && readErrorStatus(error)) {
    return `Couldn't remove ${label}. ${error.message}`
  }
  return `Couldn't remove ${label} from this agent. The knowledge base was not deleted.`
}

export function packAvailabilityLabel(pack: { hold?: boolean; ingestible?: boolean }): {
  status: "ready" | "updating" | "coming_soon" | "unavailable"
  customerLabel: string
  assignable: boolean
} {
  if (pack.hold) {
    return { status: "coming_soon", customerLabel: "Coming soon", assignable: false }
  }
  if (pack.ingestible === false) {
    return { status: "unavailable", customerLabel: "Unavailable", assignable: false }
  }
  return { status: "ready", customerLabel: "Ready", assignable: true }
}
