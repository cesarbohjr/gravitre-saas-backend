/** Shared getting-started checklist — single source for sidebar % and floating widget. */

export type OnboardingChecklistStepKey =
  | "welcome"
  | "connect"
  | "operator"
  | "task"
  | "path"
  | "next"

export type OnboardingChecklistStepDef = {
  id: string
  stepKey: OnboardingChecklistStepKey
  title: string
  description: string
  href: string
}

export const ONBOARDING_CHECKLIST_STEPS: OnboardingChecklistStepDef[] = [
  {
    id: "create-account",
    stepKey: "welcome",
    title: "Complete welcome setup",
    description: "Choose your role and finish the welcome flow",
    href: "/welcome",
  },
  {
    id: "connect-tool",
    stepKey: "connect",
    title: "Connect your first tool",
    description: "Link Slack, HubSpot, or another integration",
    href: "/connectors",
  },
  {
    id: "create-agent",
    stepKey: "operator",
    title: "Create your first agent",
    description: "Set up an AI agent to handle tasks",
    href: "/agents/new",
  },
  {
    id: "run-first-task",
    stepKey: "task",
    title: "Run your first task",
    description: "Ask Gravitre AI to execute tracked work",
    href: "/ai",
  },
  {
    id: "setup-workflow",
    stepKey: "path",
    title: "Set up your first workflow",
    description: "Create and execute an automation",
    href: "/workflows",
  },
  {
    id: "invite-team",
    stepKey: "next",
    title: "Invite a teammate",
    description: "Collaborate with your team",
    href: "/settings/organizations",
  },
]

export const ONBOARDING_CHECKLIST_STEP_KEYS = ONBOARDING_CHECKLIST_STEPS.map((step) => step.stepKey)

export const ONBOARDING_ROUTE_STEP_MAP: Array<{ prefix: string; stepKey: OnboardingChecklistStepKey }> = [
  { prefix: "/welcome", stepKey: "welcome" },
  { prefix: "/connectors", stepKey: "connect" },
  { prefix: "/agents/new", stepKey: "operator" },
  { prefix: "/ai", stepKey: "task" },
  { prefix: "/assistant", stepKey: "task" },
  { prefix: "/workflows", stepKey: "path" },
  { prefix: "/settings/organizations", stepKey: "next" },
]
