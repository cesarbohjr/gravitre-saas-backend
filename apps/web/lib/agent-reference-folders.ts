/** Cloud folder references agents use for department-specific knowledge (read-only). */

export type AgentReferenceFolderTag =
  | "marketing"
  | "hr"
  | "operations"
  | "engineering"
  | "finance"
  | "legal"
  | "sales"
  | "general"

export interface AgentReferenceFolder {
  id: string
  connectorId: string
  connectorVendor: string
  connectorName: string
  folderPath: string
  folderName: string
  label?: string
  tags: AgentReferenceFolderTag[]
}

export const REFERENCE_FOLDER_TAG_OPTIONS: Array<{
  id: AgentReferenceFolderTag
  label: string
}> = [
  { id: "marketing", label: "Marketing" },
  { id: "hr", label: "HR" },
  { id: "operations", label: "Operations" },
  { id: "engineering", label: "Engineering" },
  { id: "finance", label: "Finance" },
  { id: "legal", label: "Legal" },
  { id: "sales", label: "Sales" },
  { id: "general", label: "General" },
]

/** Vendors that support cloud folder references. */
export const CLOUD_FOLDER_VENDORS: Array<{
  vendor: string
  label: string
  connectHint: string
}> = [
  { vendor: "google_drive", label: "Google Drive", connectHint: "Connect Google Drive" },
  { vendor: "microsoft365", label: "Microsoft 365 / OneDrive", connectHint: "Connect Microsoft 365" },
  { vendor: "dropbox", label: "Dropbox Business", connectHint: "Connect Dropbox" },
  { vendor: "box", label: "Box", connectHint: "Connect Box" },
  { vendor: "tresorit", label: "Tresorit Business", connectHint: "Connect Tresorit" },
]

const TAG_KEYWORDS: Record<AgentReferenceFolderTag, string[]> = {
  marketing: ["marketing", "brand", "campaign", "creative"],
  hr: ["hr", "human resources", "people", "handbook", "policy", "policies", "employee"],
  operations: ["operations", "ops", "process", "sop"],
  engineering: ["engineering", "dev", "developer", "tech", "platform"],
  finance: ["finance", "accounting", "budget", "invoice"],
  legal: ["legal", "compliance", "contract"],
  sales: ["sales", "crm", "pipeline", "revenue"],
  general: ["shared", "company", "general"],
}

export function normalizeFolderPath(value: string): string {
  const trimmed = value.trim().replace(/\\/g, "/")
  if (!trimmed) return ""
  return trimmed.startsWith("/") ? trimmed : `/${trimmed}`
}

export function folderLeafName(path: string): string {
  const normalized = normalizeFolderPath(path)
  const parts = normalized.split("/").filter(Boolean)
  return parts[parts.length - 1] ?? normalized.replace(/^\//, "") ?? "Folder"
}

export function inferTagsFromFolderPath(path: string): AgentReferenceFolderTag[] {
  const haystack = path.toLowerCase()
  const tags = REFERENCE_FOLDER_TAG_OPTIONS.map((option) => option.id).filter((tag) =>
    TAG_KEYWORDS[tag].some((keyword) => haystack.includes(keyword)),
  )
  return tags.length > 0 ? tags : ["general"]
}

export function formatReferenceFolderBreadcrumb(folder: AgentReferenceFolder): string {
  const provider = folder.connectorName || folder.connectorVendor
  const path = normalizeFolderPath(folder.folderPath)
  const segments = path.split("/").filter(Boolean)
  return [provider, ...segments].join(" › ")
}

export function formatReferenceFolderPathOnly(folder: AgentReferenceFolder): string {
  const path = normalizeFolderPath(folder.folderPath)
  const segments = path.split("/").filter(Boolean)
  return segments.join(" › ")
}

export function tagLabel(tag: AgentReferenceFolderTag): string {
  return REFERENCE_FOLDER_TAG_OPTIONS.find((option) => option.id === tag)?.label ?? tag
}

export function readReferenceFoldersFromRecord(
  record: Record<string, unknown> | null | undefined,
): AgentReferenceFolder[] {
  if (!record) return []
  const direct = record.referenceFolders ?? record.reference_folders
  if (Array.isArray(direct)) {
    return direct.filter(isAgentReferenceFolder)
  }
  const config =
    record.config && typeof record.config === "object"
      ? (record.config as Record<string, unknown>)
      : null
  const nested = config?.referenceFolders ?? config?.reference_folders
  if (Array.isArray(nested)) {
    return nested.filter(isAgentReferenceFolder)
  }
  return []
}

function isAgentReferenceFolder(value: unknown): value is AgentReferenceFolder {
  if (!value || typeof value !== "object") return false
  const row = value as Record<string, unknown>
  return (
    typeof row.id === "string" &&
    typeof row.connectorId === "string" &&
    typeof row.folderPath === "string"
  )
}

export function createReferenceFolder(input: {
  connectorId: string
  connectorVendor: string
  connectorName: string
  folderPath: string
  label?: string
  tags?: AgentReferenceFolderTag[]
}): AgentReferenceFolder {
  const folderPath = normalizeFolderPath(input.folderPath)
  return {
    id: crypto.randomUUID(),
    connectorId: input.connectorId,
    connectorVendor: input.connectorVendor,
    connectorName: input.connectorName,
    folderPath,
    folderName: folderLeafName(folderPath),
    label: input.label?.trim() || undefined,
    tags: input.tags && input.tags.length > 0 ? input.tags : inferTagsFromFolderPath(folderPath),
  }
}
