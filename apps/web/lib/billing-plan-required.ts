export const PLAN_REQUIRED_EVENT = "gravitre:plan-required"

export type PlanRequiredDetail = {
  error?: string
  subscription_status?: string
  message?: string
  upgrade_url?: string
}

export function emitPlanRequired(detail: PlanRequiredDetail) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent(PLAN_REQUIRED_EVENT, { detail }))
  window.sessionStorage.setItem("gravitre-plan-required", JSON.stringify(detail))
}

export function readStoredPlanRequired(): PlanRequiredDetail | null {
  if (typeof window === "undefined") return null
  const raw = window.sessionStorage.getItem("gravitre-plan-required")
  if (!raw) return null
  try {
    return JSON.parse(raw) as PlanRequiredDetail
  } catch {
    return null
  }
}

export function clearStoredPlanRequired() {
  if (typeof window === "undefined") return
  window.sessionStorage.removeItem("gravitre-plan-required")
}
