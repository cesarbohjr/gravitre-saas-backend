import {
  Bell,
  Boxes,
  Brain,
  Building2,
  CreditCard,
  DollarSign,
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

export const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    id: "profile",
    title: "Profile",
    description: "Your name, avatar, and account preferences",
    icon: UserRound,
    tier: "personal",
    href: "/settings/profile",
  },
  {
    id: "organizations",
    title: "Organizations",
    description: "Switch or manage workspace membership",
    icon: Building2,
    tier: "personal",
    href: "/settings/organizations",
  },
  {
    id: "organization",
    title: "Organization",
    description: "Manage organization details and branding",
    icon: Building2,
    tier: "organization",
    href: "/settings?section=organization",
  },
  {
    id: "ai-models",
    title: "AI Models",
    description: "Configure default models, AI behavior, and Memory entity matching",
    icon: Brain,
    tier: "organization",
    href: "/settings?section=ai-models",
  },
  {
    id: "security",
    title: "Security",
    description: "Authentication, SSO, and access controls",
    icon: Shield,
    tier: "organization",
    href: "/settings?section=security",
  },
  {
    id: "api-keys",
    title: "API Keys",
    description: "Manage API keys for integrations",
    icon: Key,
    tier: "organization",
    href: "/settings?section=api-keys",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Configure alerts and notification channels",
    icon: Bell,
    tier: "organization",
    href: "/settings?section=notifications",
  },
  {
    id: "team",
    title: "Team Members",
    description: "Invite and manage team access",
    icon: Users,
    tier: "organization",
    href: "/settings?section=team",
  },
  {
    id: "lite-seats",
    title: "Lite Seats",
    description: "Allocate Gravitre Lite seats by department",
    icon: Users,
    tier: "organization",
    href: "/settings?section=lite-seats",
  },
  {
    id: "meson-addons",
    title: "Meson Addons",
    description: "Enable premium AI addon capabilities",
    icon: Sparkles,
    tier: "organization",
    href: "/settings?section=meson-addons",
  },
  {
    id: "billing",
    title: "Billing & Plan",
    description: "Subscription, payment method, and invoices",
    icon: CreditCard,
    tier: "organization",
    href: "/settings/billing",
  },
  {
    id: "billing-usage",
    title: "Billing Usage",
    description: "Review outputs and overage usage",
    icon: DollarSign,
    tier: "organization",
    href: "/settings?section=billing-usage",
  },
  {
    id: "webhooks",
    title: "Webhooks",
    description: "Configure outbound webhooks",
    icon: Webhook,
    tier: "organization",
    href: "/settings?section=webhooks",
  },
  {
    id: "permissions",
    title: "Role permissions",
    description: "What each workspace role can access",
    icon: Shield,
    tier: "admin",
    href: "/settings/team/permissions",
    adminOnly: true,
  },
  {
    id: "approvals",
    title: "Human-in-the-loop",
    description: "Require approval before high-impact actions run",
    icon: Lock,
    tier: "admin",
    href: "/settings/approvals",
    adminOnly: true,
  },
  {
    id: "enterprise",
    title: "Enterprise",
    description: "CS workspace, residency, white-label, and SIEM",
    icon: Building2,
    tier: "admin",
    href: "/settings/enterprise",
    adminOnly: true,
  },
  {
    id: "federation",
    title: "Federation",
    description: "Cross-org grants and handoffs",
    icon: Handshake,
    tier: "admin",
    href: "/settings/federation",
    adminOnly: true,
  },
  {
    id: "environments",
    title: "Environments",
    description: "Prod and staging environment controls",
    icon: Boxes,
    tier: "admin",
    href: "/environments",
    adminOnly: true,
  },
  {
    id: "audit",
    title: "Audit trail",
    description: "Review security and compliance events",
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
  "billing",
  "approvals",
  "permissions",
  "audit",
  "enterprise",
  "federation",
  "environments",
])

export function settingsHrefForSection(section: SettingsSectionId): string {
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
