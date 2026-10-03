/**
 * Map marketplace pack `department` labels onto department-pipeline keys.
 *
 * Pack seed departments and pipeline catalog keys are not the same string.
 * Customer Success and Support have no pipeline — leave them unmapped.
 */
const PACK_DEPARTMENT_TO_PIPELINE_KEY: Record<string, string> = {
  marketing: "marketing",
  sales: "sales",
  "revenue operations": "sales",
  revops: "sales",
  hr: "hr",
  "human resources": "hr",
  msp: "msp",
  operations: "msp",
  finance: "finance",
}

export function pipelineDepartmentKey(department: string | null | undefined): string | null {
  const normalized = String(department ?? "").trim().toLowerCase()
  if (!normalized || normalized === "general") return null
  return PACK_DEPARTMENT_TO_PIPELINE_KEY[normalized] ?? null
}
