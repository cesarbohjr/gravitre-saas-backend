import {
  Bell,
  Brain,
  Building2,
  CreditCard,
  DollarSign,
  Key,
  Shield,
  Sparkles,
  Users,
  Webhook,
  type LucideIcon,
} from "lucide-react"

export type SettingsSectionId =
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

export interface SettingsSection {
  id: SettingsSectionId
  title: string
  description: string
  icon: LucideIcon
  /** Prefer href so standalone routes (e.g. /settings/billing) keep a working left nav. */
  href?: string
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    id: "organization",
    title: "Organization",
    description: "Manage organization details and branding",
    icon: Building2,
    href: "/settings?section=organization",
  },
  {
    id: "ai-models",
    title: "AI Models",
    description: "Configure default models, AI behavior, and Memory entity matching",
    icon: Brain,
    href: "/settings?section=ai-models",
  },
  {
    id: "security",
    title: "Security",
    description: "Authentication, SSO, and access controls",
    icon: Shield,
    href: "/settings?section=security",
  },
  {
    id: "api-keys",
    title: "API Keys",
    description: "Manage API keys for integrations",
    icon: Key,
    href: "/settings?section=api-keys",
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Configure alerts and notification channels",
    icon: Bell,
    href: "/settings?section=notifications",
  },
  {
    id: "team",
    title: "Team Members",
    description: "Invite and manage team access",
    icon: Users,
    href: "/settings?section=team",
  },
  {
    id: "lite-seats",
    title: "Lite Seats",
    description: "Allocate Gravitre Lite seats by department",
    icon: Users,
    href: "/settings?section=lite-seats",
  },
  {
    id: "meson-addons",
    title: "Meson Addons",
    description: "Enable premium AI addon capabilities",
    icon: Sparkles,
    href: "/settings?section=meson-addons",
  },
  {
    id: "billing",
    title: "Billing & Plan",
    description: "Subscription, payment method, and invoices",
    icon: CreditCard,
    href: "/settings/billing",
  },
  {
    id: "billing-usage",
    title: "Billing Usage",
    description: "Review outputs and overage usage",
    icon: DollarSign,
    href: "/settings?section=billing-usage",
  },
  {
    id: "webhooks",
    title: "Webhooks",
    description: "Configure outbound webhooks",
    icon: Webhook,
    href: "/settings?section=webhooks",
  },
]

export const ADMIN_ONLY_SETTINGS_SECTIONS = new Set<SettingsSectionId>([
  "organization",
  "ai-models",
  "security",
  "api-keys",
  "team",
  "webhooks",
  "lite-seats",
  "meson-addons",
  "billing-usage",
  "billing",
])
