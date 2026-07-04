export type AppEnvironment = "production" | "staging"

export const ENVIRONMENT_STORAGE_KEY = "gravitre:selectedEnvironment"

const DEFAULT_ENVIRONMENT: AppEnvironment = "production"

let cachedEnvironment: AppEnvironment | undefined

export function normalizeEnvironment(value: string | null | undefined): AppEnvironment {
  const raw = String(value || DEFAULT_ENVIRONMENT).trim().toLowerCase()
  if (raw === "staging" || raw === "stage") return "staging"
  return "production"
}

export function getSelectedEnvironmentFromStorage(): AppEnvironment {
  if (typeof window === "undefined") return DEFAULT_ENVIRONMENT
  const raw = window.localStorage.getItem(ENVIRONMENT_STORAGE_KEY)
  return normalizeEnvironment(raw)
}

export function setSelectedEnvironmentInStorage(environment: AppEnvironment): void {
  if (typeof window === "undefined") return
  window.localStorage.setItem(ENVIRONMENT_STORAGE_KEY, environment)
  cachedEnvironment = environment
  window.dispatchEvent(new CustomEvent("gravitre:environment-changed", { detail: environment }))
}

export function getQuickEnvironment(): AppEnvironment {
  if (typeof window === "undefined") return DEFAULT_ENVIRONMENT
  if (cachedEnvironment) return cachedEnvironment
  cachedEnvironment = getSelectedEnvironmentFromStorage()
  return cachedEnvironment
}

export function invalidateEnvironmentCache(): void {
  cachedEnvironment = undefined
}

/** Header value for API requests — matches backend get_environment_context. */
export function getEnvironmentHeader(): string {
  return getQuickEnvironment()
}
