import {
  Armchair,
  Bell,
  Blocks,
  Briefcase,
  Building,
  Building2,
  CreditCard,
  FileClock,
  Layers,
  ShieldCheck,
  UserCheck,
  UserCog,
  HandCoins,
  KeyRound,
  Link2,
  Palette,
  PlugZap,
  Sparkles,
  UserRound,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react"

export type SettingsTier = "personal" | "organization" | "admin"

/** Left-nav groups from the Dashboard settings design: Account, Workspace, People and plan, Advanced, Governance. */
export type SettingsGroup = "account" | "workspace" | "people" | "advanced" | "governance"

export const SETTINGS_GROUPS: { id: SettingsGroup; label: string; hint?: string; locked?: boolean }[] = [
  { id: "account", label: "Account" },
  { id: "workspace", label: "Workspace" },
  { id: "people", label: "People and plan" },
  { id: "advanced", label: "Advanced", hint: "Admins only" },
  { id: "governance", label: "Governance", hint: "Admins only" },
]

export type SettingsSectionId =
  | "profile"
  | "organizations"
  | "organization"
  | "ai-models"
  | "api-keys"
  | "notifications"
  | "team"
  | "lite-seats"
  | "meson-addons"
  | "billing-usage"
  | "billing"
  | "webhooks"
  | "audit"
  | "security"
  | "roles"
  | "hitl"
  | "environments"
  | "enterprise"
  | "federation"
  | "clients"
  | "branding"
  | "mcp-servers"

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
    id: "branding",
    title: "Branding",
    description: "Your logo, accent color, sender name and custom domain, shown to everyone in this workspace.",
    group: "workspace",
    icon: Palette,
    tier: "admin",
    href: "/settings?section=branding",
    adminOnly: true,
  },
  {
    id: "ai-models",
    title: "AI models",
    description: "How Gravitre picks models for your agents, how chat memory matches the people and channels you mention, and which customer data it may use.",
    group: "workspace",
    icon: Sparkles,
    tier: "organization",
    href: "/settings?section=ai-models",
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
      "For MSPs reselling Gravitre. You pay Gravitre the wholesale price for each client workspace and bill them your own price. The difference is your margin.",
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
    id: "enterprise",
    title: "Enterprise",
    description: "Reports for admins: integration health, agent work by team, cost and agent ROI.",
    group: "advanced",
    icon: Briefcase,
    tier: "admin",
    href: "/settings/enterprise",
    adminOnly: true,
  },
  {
    id: "federation",
    title: "Federation and B2B",
    description: "Work with another company as an equal partner. Both sides must consent before any agent handoff, connector grant or delegated task crosses org boundaries. Billing is not shared.",
    group: "advanced",
    icon: Link2,
    tier: "admin",
    href: "/settings/federation",
    adminOnly: true,
  },
  {
    id: "mcp-servers",
    title: "MCP servers",
    description: "Connect outside MCP servers so your agents can use their tools.",
    group: "advanced",
    icon: PlugZap,
    tier: "admin",
    href: "/marketplace/capabilities?filter=mcp#mcp-servers",
    adminOnly: true,
  },
  // Security, role permissions, environments and the audit trail have their own
  // settings pages built on the Trust & Safety panels; approval rules stay a
  // Trust & Safety tab.
  {
    id: "security",
    title: "Security",
    description: "Sign in, single sign on and access controls for everyone in this workspace.",
    group: "workspace",
    icon: ShieldCheck,
    tier: "organization",
    href: "/settings/security",
  },
  {
    id: "roles",
    title: "Role permissions",
    description: "What each workspace role can do. Roles come from your organization's role definitions.",
    group: "people",
    icon: UserCog,
    tier: "admin",
    href: "/settings/roles",
    adminOnly: true,
  },
  {
    id: "hitl",
    title: "Human in the loop",
    description: "Which actions wait for a person, and how risk decides who approves.",
    group: "advanced",
    icon: UserCheck,
    tier: "admin",
    href: "/trust-safety?tab=policies",
    adminOnly: true,
  },
  {
    id: "environments",
    title: "Environments",
    description: "Where your agents and workflows run, and how changes move from testing to production.",
    group: "governance",
    icon: Layers,
    tier: "admin",
    href: "/settings/environments",
    adminOnly: true,
  },
  {
    id: "audit",
    title: "Audit trail",
    description: "Who did what, when, and how it turned out.",
    group: "governance",
    icon: FileClock,
    tier: "admin",
    href: "/settings/audit",
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
  "enterprise",
  "federation",
  "team",
  "api-keys",
  "webhooks",
  "lite-seats",
  "meson-addons",
  "ai-models",
  "clients",
  "branding",
  "security",
  "roles",
  "audit",
  "environments",
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
  // Workspace
  organizations: 0,
  organization: 1,
  branding: 1.5,
  security: 2,
  "api-keys": 3,
  notifications: 4,
  "ai-models": 5,
  webhooks: 6,
  // People and plan
  team: 0,
  roles: 1,
  "lite-seats": 2,
  billing: 3,
  "meson-addons": 4,
  clients: 5,
  // Advanced
  federation: 0,
  enterprise: 1,
  hitl: 2,
  "mcp-servers": 3,
  // Governance
  audit: 0,
  environments: 1,
}

export function settingsSectionsForGroup(group: SettingsGroup, isAdmin: boolean): SettingsSection[] {
  return SETTINGS_SECTIONS.filter((section) => section.group === group && (!section.adminOnly || isAdmin)).sort(
    (a, b) => (GROUP_ORDER[a.id] ?? 0) - (GROUP_ORDER[b.id] ?? 0),
  )
}

export function settingsGroupLabel(group: SettingsGroup): string {
  return SETTINGS_GROUPS.find((row) => row.id === group)?.label ?? "Settings"
}
