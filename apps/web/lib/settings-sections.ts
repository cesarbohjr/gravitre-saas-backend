import {
  Armchair,
  Bell,
  Blocks,
  Briefcase,
  Building,
  Building2,
  CreditCard,
  Hand,
  HandCoins,
  KeyRound,
  Link2,
  ListChecks,
  Lock,
  Server,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react"

export type SettingsTier = "personal" | "organization" | "admin"

/** Left-nav groups from the Settings Pages Redesign: Account, Workspace, People and plan, Advanced, Governance. */
export type SettingsGroup = "account" | "workspace" | "people" | "advanced" | "governance"

export const SETTINGS_GROUPS: { id: SettingsGroup; label: string; locked?: boolean }[] = [
  { id: "account", label: "Account" },
  { id: "workspace", label: "Workspace" },
  { id: "people", label: "People and plan" },
  { id: "advanced", label: "Advanced" },
  { id: "governance", label: "Governance" },
]

export type SettingsSectionId =
  | "profile"
  | "organizations"
  | "organization"
  | "ai-models"
  | "security"
  | "api-keys"
  | "notifications"
  | "team"
  | "lite-seats"
  | "meson-addons"
  | "billing-usage"
  | "billing"
  | "webhooks"
  | "permissions"
  | "approvals"
  | "audit"
  | "enterprise"
  | "federation"
  | "environments"
  | "clients"

export interface SettingsSection {
  id: SettingsSectionId
  title: string
  description: string
  icon: LucideIcon
  tier: SettingsTier
  group: SettingsGroup
  /** Prefer href so standalone routes keep a working left nav. */
  href?: string
  /** Hide from the primary list; still valid as activeSection. */
  footer?: boolean
  adminOnly?: boolean
}

export const SETTINGS_TIER_LABELS: Record<SettingsTier, string> = {
  personal: "Personal",
  organization: "Organization",
  admin: "Admin",
}

/** Who a change in this tier affects — shown beside every settings title. */
export const SETTINGS_TIER_SCOPE: Record<SettingsTier, { label: string; detail: string }> = {
  personal: { label: "Only you", detail: "Changes apply to your account only." },
  organization: { label: "Whole organization", detail: "Changes apply to everyone in this workspace." },
  admin: { label: "Admins only", detail: "Restricted to owners and admins. Every change is recorded in the audit log." },
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    id: "profile",
    title: "Profile",
    description: "Your name, photo, preferences and active sessions",
    group: "account",
    icon: UserRound,
    tier: "personal",
    href: "/settings/profile",
  },
  {
    id: "organizations",
    title: "Organizations",
    description: "Each organization has its own agents, workflows and billing. Pick one to see its details or switch to it.",
    group: "workspace",
    icon: Building,
    tier: "personal",
    href: "/settings/organizations",
  },
  {
    id: "organization",
    title: "General",
    description: "Name, logo and defaults for everyone in this workspace.",
    group: "workspace",
    icon: Building2,
    tier: "organization",
    href: "/settings?section=organization",
  },
  {
    id: "ai-models",
    title: "AI models",
    description: "How Gravitre picks models for your agents, and how chat memory matches the people and channels you mention.",
    group: "workspace",
    icon: Sparkles,
    tier: "organization",
    href: "/settings?section=ai-models",
  },
  {
    id: "security",
    title: "Security",
    description: "Sign in, single sign on and access controls for everyone in this workspace.",
    group: "workspace",
    icon: Lock,
    tier: "organization",
    href: "/settings?section=security",
  },
  {
    id: "api-keys",
    title: "API keys",
    description: "Keys let your own systems call Gravitre. Each key only sees what its scope allows.",
    group: "workspace",
    icon: KeyRound,
    tier: "organization",
    href: "/settings?section=api-keys",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Choose where each kind of update reaches you. Urgent things default to more places, digests to fewer.",
    group: "workspace",
    icon: Bell,
    tier: "organization",
    href: "/settings?section=notifications",
  },
  {
    id: "team",
    title: "Team members",
    description: "Invite people, set their role and see who has access.",
    group: "people",
    icon: Users,
    tier: "organization",
    href: "/settings?section=team",
  },
  {
    id: "lite-seats",
    title: "Lite seats",
    description: "Give approvers and occasional users a Lite seat by department. Lite users can run assigned workflows and approve work, but building still needs a full seat.",
    group: "people",
    icon: Armchair,
    tier: "organization",
    href: "/settings?section=lite-seats",
  },
  {
    id: "meson-addons",
    title: "Meson add-ons",
    description: "Enable premium AI addon capabilities",
    group: "people",
    icon: Blocks,
    tier: "organization",
    href: "/settings?section=meson-addons",
  },
  {
    id: "billing",
    title: "Billing and plan",
    description: "Your plan, usage this period, invoices and payment method.",
    group: "people",
    icon: CreditCard,
    tier: "organization",
    href: "/settings/billing",
  },
  {
    id: "clients",
    title: "Clients",
    description:
      "Partner program for MSPs. You pay Gravitre the wholesale price for each client and bill them your own price. The difference is your margin.",
    group: "people",
    icon: HandCoins,
    tier: "organization",
    href: "/settings/clients",
  },
  {
    id: "webhooks",
    title: "Webhooks",
    description: "Configure outbound webhooks",
    group: "workspace",
    icon: Webhook,
    tier: "organization",
    href: "/settings?section=webhooks",
  },
  {
    id: "permissions",
    title: "Role permissions",
    description: "What each workspace role can do. Roles come from your organization\'s role definitions.",
    group: "people",
    icon: ShieldCheck,
    tier: "admin",
    href: "/settings/team/permissions",
    adminOnly: true,
  },
  {
    id: "approvals",
    title: "Human in the loop",
    description: "Decide which agent actions wait for a person, and how fast someone must answer.",
    group: "governance",
    icon: Hand,
    tier: "admin",
    href: "/settings/approvals",
    adminOnly: true,
  },
  {
    id: "enterprise",
    title: "Enterprise",
    description: "Advanced controls for data residency, white labeling, workforce analytics and security.",
    group: "advanced",
    icon: Briefcase,
    tier: "admin",
    href: "/settings/enterprise",
    adminOnly: true,
  },
  {
    id: "federation",
    title: "Federation and B2B",
    description: "Work with partner organizations safely. Both sides must consent before any agent handoff, connector grant or delegated task crosses org boundaries.",
    group: "advanced",
    icon: Link2,
    tier: "admin",
    href: "/settings/federation",
    adminOnly: true,
  },
  {
    id: "environments",
    title: "Environments",
    description: "Where your agents and workflows run, and how changes move from testing to production.",
    group: "governance",
    icon: Server,
    tier: "admin",
    href: "/environments",
    adminOnly: true,
  },
  {
    id: "audit",
    title: "Audit trail",
    description: "Who did what, when, and how it turned out.",
    group: "governance",
    icon: ListChecks,
    tier: "admin",
    href: "/audit",
    adminOnly: true,
  },
]

export const PRIMARY_SETTINGS_SECTIONS = SETTINGS_SECTIONS.filter((section) => !section.footer)
export const FOOTER_SETTINGS_SECTIONS = SETTINGS_SECTIONS.filter((section) => section.footer)

export const ADMIN_ONLY_SETTINGS_SECTIONS = new Set<SettingsSectionId>(
  SETTINGS_SECTIONS.filter((section) => section.adminOnly).map((section) => section.id),
)

export const WIDE_SETTINGS_SECTIONS = new Set<SettingsSectionId>([
  // profile (4xl hero + 3-column grid) and organizations (5xl) render their own
  // wide layouts, so they'd be crushed by the shell's default max-w-2xl.
  "profile",
  "organizations",
  "billing",
  "approvals",
  "permissions",
  "audit",
  "enterprise",
  "federation",
  "environments",
  "team",
  "security",
  "api-keys",
  "webhooks",
  "lite-seats",
  "meson-addons",
  "ai-models",
  "clients",
])

export function settingsHrefForSection(section: SettingsSectionId): string {
  if (section === "billing-usage") return "/settings/billing"
  return SETTINGS_SECTIONS.find((row) => row.id === section)?.href || `/settings?section=${section}`
}

export function settingsSectionsForTier(
  tier: SettingsTier,
  isAdmin: boolean,
): SettingsSection[] {
  return SETTINGS_SECTIONS.filter((section) => {
    if (section.tier !== tier) return false
    if (section.adminOnly && !isAdmin) return false
    return true
  })
}


/** Order inside each group, following the redesign's sidebar. */
const GROUP_ORDER: Partial<Record<SettingsSectionId, number>> = {
  organizations: 0,
  organization: 1,
  security: 2,
  "api-keys": 3,
  notifications: 4,
  webhooks: 5,
  "ai-models": 6,
  team: 0,
  permissions: 1,
  "lite-seats": 2,
  "meson-addons": 3,
  billing: 4,
  clients: 5,
  federation: 0,
  enterprise: 1,
  audit: 0,
  environments: 1,
  approvals: 2,
}

export function settingsSectionsForGroup(group: SettingsGroup, isAdmin: boolean): SettingsSection[] {
  return SETTINGS_SECTIONS.filter((section) => section.group === group && (!section.adminOnly || isAdmin)).sort(
    (a, b) => (GROUP_ORDER[a.id] ?? 0) - (GROUP_ORDER[b.id] ?? 0),
  )
}

export function settingsGroupLabel(group: SettingsGroup): string {
  return SETTINGS_GROUPS.find((row) => row.id === group)?.label ?? "Settings"
}
