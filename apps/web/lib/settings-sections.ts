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
  href?: string
}

export const SETTINGS_SECTIONS: SettingsSection[] = [
  { id: "organization", title: "Organization", description: "Manage organization details and branding", icon: Building2 },
  { id: "ai-models", title: "AI Models", description: "Configure default models, AI behavior, and Memory entity matching", icon: Brain },
  { id: "security", title: "Security", description: "Authentication, SSO, and access controls", icon: Shield },
  { id: "api-keys", title: "API Keys", description: "Manage API keys for integrations", icon: Key },
  { id: "notifications", title: "Notifications", description: "Configure alerts and notification channels", icon: Bell },
  { id: "team", title: "Team Members", description: "Invite and manage team access", icon: Users },
  { id: "lite-seats", title: "Lite Seats", description: "Allocate Gravitre Lite seats by department", icon: Users },
  { id: "meson-addons", title: "Meson Addons", description: "Enable premium AI addon capabilities", icon: Sparkles },
  {
    id: "billing",
    title: "Billing & Plan",
    description: "Subscription, payment method, and invoices",
    icon: CreditCard,
    href: "/settings/billing",
  },
  { id: "billing-usage", title: "Billing Usage", description: "Review outputs and overage usage", icon: DollarSign },
  { id: "webhooks", title: "Webhooks", description: "Configure outbound webhooks", icon: Webhook },
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
