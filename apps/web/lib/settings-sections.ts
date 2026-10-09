import {
  Bell,
  Boxes,
  Brain,
  Building2,
  CreditCard,
  FileText,
  Handshake,
  Key,
  Lock,
  Shield,
  Sparkles,
  UserRound,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react"

export type SettingsTier = "personal" | "organization" | "admin"

/** Left-nav groups from the v5 Settings design, plus "account" for personal pages. */
export type SettingsGroup = "workspace" | "people" | "admin" | "account"

export const SETTINGS_GROUPS: { id: SettingsGroup; label: string; locked?: boolean }[] = [
  { id: "workspace", label: "Workspace" },
  { id: "people", label: "People and plan" },
  { id: "admin", label: "Admin", locked: true },
  { id: "account", label: "Your account" },
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
    description: "Your name, avatar, and account preferences",
    group: "account",
    icon: UserRound,
    tier: "personal",
    href: "/settings/profile",
  },
  {
    id: "organizations",
    title: "Organizations",
    description: "Switch or manage workspace membership",
    group: "account",
    icon: Building2,
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
    description: "Configure default models, AI behavior, and Memory entity matching",
    group: "workspace",
    icon: Brain,
    tier: "organization",
    href: "/settings?section=ai-models",
  },
  {
    id: "security",
    title: "Security",
    description: "Authentication, SSO, and access controls",
    group: "workspace",
    icon: Shield,
    tier: "organization",
    href: "/settings?section=security",
  },
  {
    id: "api-keys",
    title: "API keys",
    description: "Manage API keys for integrations",
    group: "workspace",
    icon: Key,
    tier: "organization",
    href: "/settings?section=api-keys",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Choose where each kind of update reaches you.",
    group: "workspace",
    icon: Bell,
    tier: "organization",
    href: "/settings?section=notifications",
  },
  {
    id: "team",
    title: "Team members",
    description: "Invite and manage team access",
    group: "people",
    icon: Users,
    tier: "organization",
    href: "/settings?section=team",
  },
  {
    id: "lite-seats",
    title: "Lite seats",
    description: "Allocate Gravitre Lite seats by department",
    group: "people",
    icon: Users,
    tier: "organization",
    href: "/settings?section=lite-seats",
  },
  {
    id: "meson-addons",
    title: "Meson add-ons",
    description: "Enable premium AI addon capabilities",
    group: "people",
    icon: Sparkles,
    tier: "organization",
    href: "/settings?section=meson-addons",
  },
  {
    id: "billing",
    title: "Billing and plan",
    description: "Subscription, usage, top-ups, and invoices",
    group: "people",
    icon: CreditCard,
    tier: "organization",
    href: "/settings/billing",
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
    description: "What each workspace role can access",
    group: "admin",
    icon: Shield,
    tier: "admin",
    href: "/settings/team/permissions",
    adminOnly: true,
  },
  {
    id: "approvals",
    title: "Human in the loop",
    description: "Decide which agent actions wait for a person, and how fast someone must answer.",
    group: "admin",
    icon: Lock,
    tier: "admin",
    href: "/settings/approvals",
    adminOnly: true,
  },
  {
    id: "enterprise",
    title: "Enterprise",
    description: "CS workspace, residency, white-label, and SIEM",
    group: "admin",
    icon: Building2,
    tier: "admin",
    href: "/settings/enterprise",
    adminOnly: true,
  },
  {
    id: "federation",
    title: "Federation",
    description: "Cross-org grants and handoffs",
    group: "admin",
    icon: Handshake,
    tier: "admin",
    href: "/settings/federation",
    adminOnly: true,
  },
  {
    id: "environments",
    title: "Environments",
    description: "Prod and staging environment controls",
    group: "admin",
    icon: Boxes,
    tier: "admin",
    href: "/environments",
    adminOnly: true,
  },
  {
    id: "audit",
    title: "Audit trail",
    description: "Review security and compliance events",
    group: "admin",
    icon: FileText,
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


/** Workspace group in the design's order: General, Security, API keys, Notifications, Webhooks. */
const GROUP_ORDER: Partial<Record<SettingsSectionId, number>> = {
  organization: 0,
  security: 1,
  "api-keys": 2,
  notifications: 3,
  webhooks: 4,
  "ai-models": 5,
}

export function settingsSectionsForGroup(group: SettingsGroup, isAdmin: boolean): SettingsSection[] {
  return SETTINGS_SECTIONS.filter((section) => section.group === group && (!section.adminOnly || isAdmin)).sort(
    (a, b) => (GROUP_ORDER[a.id] ?? 0) - (GROUP_ORDER[b.id] ?? 0),
  )
}

export function settingsGroupLabel(group: SettingsGroup): string {
  return SETTINGS_GROUPS.find((row) => row.id === group)?.label ?? "Settings"
}
