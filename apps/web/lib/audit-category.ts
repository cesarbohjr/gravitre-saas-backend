import {
  Activity,
  Bot,
  CreditCard,
  Database,
  FileText,
  Globe,
  KeyRound,
  Settings,
  Share2,
  ShieldCheck,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react"

export type AuditCategory =
  | "agent"
  | "workflow"
  | "connector"
  | "auth"
  | "billing"
  | "federation"
  | "security"
  | "data"
  | "settings"
  | "user"
  | "system"

type CategoryStyle = {
  label: string
  icon: LucideIcon
  // Foreground accent token + matching soft background + left-edge border.
  text: string
  soft: string
  edge: string
}

// Maps an audit category to a stable glyph + semantic accent so each event type
// is scannable at a glance. Colors stay within the design token system.
export const AUDIT_CATEGORY_STYLES: Record<AuditCategory, CategoryStyle> = {
  agent: { label: "Agent", icon: Bot, text: "text-info", soft: "bg-info/10", edge: "border-l-info" },
  workflow: { label: "Workflow", icon: Workflow, text: "text-primary", soft: "bg-primary/10", edge: "border-l-primary" },
  connector: { label: "Connector", icon: Share2, text: "text-info", soft: "bg-info/10", edge: "border-l-info" },
  auth: { label: "Auth", icon: KeyRound, text: "text-warning", soft: "bg-warning/10", edge: "border-l-warning" },
  billing: { label: "Billing", icon: CreditCard, text: "text-success", soft: "bg-success/10", edge: "border-l-success" },
  federation: { label: "Federation", icon: Globe, text: "text-primary", soft: "bg-primary/10", edge: "border-l-primary" },
  security: { label: "Security", icon: ShieldCheck, text: "text-destructive", soft: "bg-destructive/10", edge: "border-l-destructive" },
  data: { label: "Data", icon: Database, text: "text-info", soft: "bg-info/10", edge: "border-l-info" },
  settings: { label: "Settings", icon: Settings, text: "text-muted-foreground", soft: "bg-muted", edge: "border-l-border" },
  user: { label: "User", icon: Users, text: "text-foreground", soft: "bg-muted", edge: "border-l-foreground/40" },
  system: { label: "System", icon: Activity, text: "text-muted-foreground", soft: "bg-muted", edge: "border-l-border" },
}

const FALLBACK: CategoryStyle = {
  label: "Event",
  icon: FileText,
  text: "text-muted-foreground",
  soft: "bg-muted",
  edge: "border-l-border",
}

// Derives a category from an audit event's entity type / action string. Keeps
// classification resilient to varied backend vocab via keyword matching.
export function categorizeAuditEvent(input: {
  entityType?: string | null
  action?: string | null
  category?: string | null
}): CategoryStyle {
  const haystack = `${input.category ?? ""} ${input.entityType ?? ""} ${input.action ?? ""}`.toLowerCase()

  const match = (...keys: string[]) => keys.some((k) => haystack.includes(k))

  if (match("agent")) return AUDIT_CATEGORY_STYLES.agent
  if (match("swarm", "workflow", "run", "task")) return AUDIT_CATEGORY_STYLES.workflow
  if (match("connector", "integration")) return AUDIT_CATEGORY_STYLES.connector
  if (match("federation", "partner", "trust")) return AUDIT_CATEGORY_STYLES.federation
  if (match("login", "logout", "session", "token", "auth", "api key", "apikey")) return AUDIT_CATEGORY_STYLES.auth
  if (match("billing", "invoice", "payment", "subscription", "plan")) return AUDIT_CATEGORY_STYLES.billing
  if (match("security", "permission", "role", "policy", "breach", "block")) return AUDIT_CATEGORY_STYLES.security
  if (match("data", "export", "import", "record", "document", "dataset")) return AUDIT_CATEGORY_STYLES.data
  if (match("setting", "config", "preference")) return AUDIT_CATEGORY_STYLES.settings
  if (match("user", "member", "account", "invite")) return AUDIT_CATEGORY_STYLES.user
  if (match("system", "cron", "scheduled")) return AUDIT_CATEGORY_STYLES.system

  return FALLBACK
}
