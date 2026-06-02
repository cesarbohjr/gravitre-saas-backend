declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void
  }
}

export type SignupEventName =
  | "signup_page_viewed"
  | "signup_started"
  | "signup_oauth_clicked"
  | "signup_form_submitted"
  | "signup_completed"
  | "signup_failed"
  | "onboarding_bootstrap_started"
  | "onboarding_bootstrap_completed"
  | "onboarding_step_completed"

export function getUtmParams(): Record<string, string> {
  if (typeof window === "undefined") return {}
  const params = new URLSearchParams(window.location.search)
  const utm: Record<string, string> = {}
  for (const key of ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"]) {
    const value = params.get(key)
    if (value) utm[key] = value
  }
  return utm
}

/** Fire signup funnel events — never throws or blocks UI. */
export function trackSignupEvent(
  name: SignupEventName,
  props?: Record<string, string | number | boolean | undefined>
): void {
  try {
    if (process.env.NODE_ENV === "development") {
      console.debug("[analytics]", name, props ?? {})
    }

    if (typeof window !== "undefined" && typeof window.gtag === "function") {
      window.gtag("event", name, props ?? {})
    }

    if (typeof window !== "undefined") {
      void fetch("/api/analytics/events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, props, ts: Date.now() }),
      }).catch(() => {})
    }
  } catch {
    // Analytics must never block auth flows
  }
}
