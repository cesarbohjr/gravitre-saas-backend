/** Selected department scope for cowork desk — drives RAG, persona, and Lite filtering. */

export type DepartmentScope = string

export const DEPARTMENT_STORAGE_KEY = "gravitre:selectedDepartment"
export const DEPARTMENT_ALL = "all"

const DEFAULT_DEPARTMENT: DepartmentScope = DEPARTMENT_ALL

let cachedDepartment: DepartmentScope | undefined

export const DEPARTMENT_OPTIONS = [
  { id: DEPARTMENT_ALL, label: "All departments" },
  { id: "Marketing", label: "Marketing" },
  { id: "Sales", label: "Sales" },
  { id: "Finance", label: "Finance" },
  { id: "Support", label: "Support" },
  { id: "Operations", label: "Operations" },
  { id: "Engineering", label: "Engineering" },
  { id: "HR", label: "HR" },
] as const

export function normalizeDepartmentScope(value: string | null | undefined): DepartmentScope {
  const raw = String(value || DEFAULT_DEPARTMENT).trim()
  if (!raw || raw.toLowerCase() === "all") return DEPARTMENT_ALL
  return raw
}

export function getSelectedDepartmentFromStorage(): DepartmentScope {
  if (typeof window === "undefined") return DEFAULT_DEPARTMENT
  return normalizeDepartmentScope(window.localStorage.getItem(DEPARTMENT_STORAGE_KEY))
}

export function setSelectedDepartmentInStorage(department: DepartmentScope): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(DEPARTMENT_STORAGE_KEY, normalizeDepartmentScope(department))
  cachedDepartment = normalizeDepartmentScope(department)
  window.dispatchEvent(
    new CustomEvent("gravitre:department-changed", { detail: cachedDepartment }),
  )
}

export function getQuickDepartment(): DepartmentScope {
  if (typeof window === "undefined") return DEFAULT_DEPARTMENT
  if (cachedDepartment) return cachedDepartment
  cachedDepartment = getSelectedDepartmentFromStorage()
  return cachedDepartment
}

export function invalidateDepartmentCache(): void {
  cachedDepartment = undefined
}

/** Header for API requests — omitted when "all". */
export function getDepartmentHeader(): string | undefined {
  const dept = getQuickDepartment()
  return dept === DEPARTMENT_ALL ? undefined : dept
}

export function isCrossDepartmentPrompt(prompt: string): boolean {
  const text = prompt.toLowerCase()
  const departments = ["marketing", "sales", "finance", "support", "operations", "engineering", "hr"]
  const hits = departments.filter((d) => text.includes(d))
  return hits.length >= 2 || /\b(hand off|handoff|cross.?department|both teams)\b/.test(text)
}
