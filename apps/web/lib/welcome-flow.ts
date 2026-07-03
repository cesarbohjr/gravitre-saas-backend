/** Shared welcome / first-run configuration. */

export type WelcomeRoleId =
  | "executive"
  | "marketing"
  | "sales"
  | "ops"
  | "hr"
  | "finance"
  | "support"
  | "engineering"

export type WelcomeRole = {
  id: WelcomeRoleId
  label: string
  description: string
  packSlug?: string
  suggestedPrompt: string
}

export const WELCOME_ROLES: WelcomeRole[] = [
  {
    id: "executive",
    label: "CEO / Executive",
    description: "ROI, risk, and org-wide intelligence",
    suggestedPrompt: "Summarize what Gravitre learned about our business this week.",
  },
  {
    id: "marketing",
    label: "Marketing",
    description: "Campaigns, attribution, and content ops",
    packSlug: "marketing-operations-pack",
    suggestedPrompt: "Draft a weekly marketing performance brief from our connected tools.",
  },
  {
    id: "sales",
    label: "Sales",
    description: "Pipeline, CRM, and revenue motions",
    packSlug: "revenue-operations-pack",
    suggestedPrompt: "Which deals need attention in our pipeline this week?",
  },
  {
    id: "ops",
    label: "Operations",
    description: "Workflows, bottlenecks, and automation",
    suggestedPrompt: "Find workflow bottlenecks and suggest one automation to fix first.",
  },
  {
    id: "hr",
    label: "HR",
    description: "Policy lookup and onboarding workflows",
    packSlug: "hr-operations-pack",
    suggestedPrompt: "Summarize onboarding checklist steps for a new hire.",
  },
  {
    id: "finance",
    label: "Finance",
    description: "Invoices, budgets, and revenue signals",
    suggestedPrompt: "Summarize overdue receivables and cash-flow risks.",
  },
  {
    id: "support",
    label: "Customer Success",
    description: "Tickets, KB, and retention",
    packSlug: "customer-success-pack",
    suggestedPrompt: "Triage open support tickets by urgency and draft first responses.",
  },
  {
    id: "engineering",
    label: "Engineering",
    description: "Incidents, PRs, and deploy status",
    suggestedPrompt: "Summarize open incidents and failed workflow runs from the last 24 hours.",
  },
]

export const WELCOME_CONNECTORS = [
  { type: "hubspot", label: "HubSpot", href: "/connectors?type=hubspot" },
  { type: "salesforce", label: "Salesforce", href: "/connectors?type=salesforce" },
  { type: "slack", label: "Slack", href: "/connectors?type=slack" },
  { type: "google_analytics", label: "Google Analytics", href: "/connectors?type=google_analytics" },
  { type: "jira", label: "Jira", href: "/connectors?type=jira" },
  { type: "stripe", label: "Stripe", href: "/connectors?type=stripe" },
] as const

export const WELCOME_STORAGE_KEY = "gravitre-welcome-completed"
export const WELCOME_DRAFT_STORAGE_KEY = "gravitre-welcome-draft"

export type WelcomeDraft = {
  stepIndex: number
  role: WelcomeRoleId | null
  skippedConnect: boolean
  selectedConnector: string | null
}

export function readWelcomeDraft(): WelcomeDraft | null {
  if (typeof window === "undefined") return null
  try {
    const raw = sessionStorage.getItem(WELCOME_DRAFT_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as WelcomeDraft
    if (typeof parsed.stepIndex !== "number") return null
    return {
      stepIndex: Math.min(Math.max(parsed.stepIndex, 0), 4),
      role: WELCOME_ROLES.some((entry) => entry.id === parsed.role) ? parsed.role : null,
      skippedConnect: Boolean(parsed.skippedConnect),
      selectedConnector:
        WELCOME_CONNECTORS.some((entry) => entry.type === parsed.selectedConnector)
          ? parsed.selectedConnector
          : null,
    }
  } catch {
    return null
  }
}

export function writeWelcomeDraft(draft: WelcomeDraft): void {
  if (typeof window === "undefined") return
  sessionStorage.setItem(WELCOME_DRAFT_STORAGE_KEY, JSON.stringify(draft))
}

export function clearWelcomeDraft(): void {
  if (typeof window === "undefined") return
  sessionStorage.removeItem(WELCOME_DRAFT_STORAGE_KEY)
}

export function readWelcomeCompletedLocal(): boolean {
  if (typeof window === "undefined") return false
  return localStorage.getItem(WELCOME_STORAGE_KEY) === "true"
}

export function markWelcomeCompletedLocal(): void {
  if (typeof window === "undefined") return
  localStorage.setItem(WELCOME_STORAGE_KEY, "true")
}

export function roleFromOnboardingStepData(stepData: Record<string, unknown> | undefined): WelcomeRoleId | null {
  const roleStep = stepData?.role
  if (!roleStep || typeof roleStep !== "object") return null
  const selected = (roleStep as { selected_role?: string }).selected_role
  if (!selected) return null
  const match = WELCOME_ROLES.find((r) => r.id === selected)
  return match?.id ?? null
}
