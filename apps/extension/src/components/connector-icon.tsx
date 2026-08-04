import { Building2, Linkedin, Mail, Slack, Cloud } from "lucide-react"

import { cn } from "@/lib/cn"
import type { Surface } from "@/lib/types"
import { VendorLogo, hasVendorLogo } from "@/components/vendor-logo"

/**
 * Icon language (Part E.3).
 *
 * Surfaces use Lucide's own permissively-drawn glyphs so the set stays visually
 * consistent with the main app, which is Lucide throughout. Vendors that have
 * no Lucide glyph (HubSpot, Apollo) get a monogram chip rather than a traced
 * logo — deliberately "recognisable, not licensed-logo-heavy".
 */

const SURFACE_ICONS: Record<Surface, typeof Mail> = {
  linkedin: Linkedin,
  gmail: Mail,
  outlook: Mail,
  salesforce: Cloud,
  slack: Slack,
  company: Building2,
  unknown: Building2,
}

export function SurfaceIcon({
  surface,
  className,
}: {
  surface: Surface
  className?: string
}) {
  // A detected surface IS a vendor ("LinkedIn profile", "Gmail thread"), so show
  // that vendor's real mark. `company`/`unknown` have no vendor and keep the
  // Lucide glyph.
  if (hasVendorLogo(surface)) {
    return <VendorLogo name={surface} className={cn("h-3.5 w-3.5", className)} />
  }

  const Icon = SURFACE_ICONS[surface] ?? Building2
  return <Icon aria-hidden="true" className={cn("h-3.5 w-3.5", className)} />
}

/** Vendor accent hues, kept within the app's existing token palette. */
const VENDOR_TONE: Record<string, string> = {
  hubspot: "text-warning",
  apollo: "text-info",
  salesforce: "text-info",
  slack: "text-foreground",
  gmail: "text-destructive",
  google: "text-destructive",
  outlook: "text-info",
  microsoft: "text-info",
  linkedin: "text-info",
}

function toneFor(name: string) {
  const key = name.toLowerCase()
  for (const vendor of Object.keys(VENDOR_TONE)) {
    if (key.includes(vendor)) return VENDOR_TONE[vendor]
  }
  return "text-muted-foreground"
}

/**
 * Human label for a connector id: `hubspot` -> "Hubspot", `google_ads` ->
 * "Google ads". Server ids are snake_cased, and raw ids in the UI read like
 * debug output.
 */
/**
 * Vendors that don't survive naive capitalisation. Showing "Hubspot" or
 * "Linkedin" next to the official mark reads as careless, and these names are
 * the load-bearing detail on the approval card.
 */
const PROPER_NAMES: Record<string, string> = {
  hubspot: "HubSpot",
  linkedin: "LinkedIn",
  github: "GitHub",
  microsoft365: "Microsoft 365",
  salesforce: "Salesforce",
  pipedrive: "Pipedrive",
  zendesk: "Zendesk",
  gmail: "Gmail",
  outlook: "Outlook",
  jira: "Jira",
  clickup: "ClickUp",
  bamboohr: "BambooHR",
  quickbooks: "QuickBooks",
  netsuite: "NetSuite",
  sendgrid: "SendGrid",
  stackadapt: "StackAdapt",
  postgresql: "PostgreSQL",
  mongodb: "MongoDB",
  mysql: "MySQL",
  openai: "OpenAI",
  xai: "xAI",
  n8n: "n8n",
}

export function connectorLabel(name: string): string {
  const raw = String(name || "").trim()
  if (!raw) return "Connector"

  const key = raw.toLowerCase().replace(/[^a-z0-9]/g, "")
  if (PROPER_NAMES[key]) return PROPER_NAMES[key]

  const label = raw.replace(/[_-]/g, " ")
  return label.charAt(0).toUpperCase() + label.slice(1)
}

/**
 * Mark for a connector: the official vendor logo where we have one, and a
 * tinted monogram otherwise.
 *
 * This used to be monogram-only. That made every connector look alike at a
 * glance, which is a real problem on the approval card where the vendor is the
 * single most important thing to read before a write goes out.
 */
export function ConnectorIcon({
  name,
  className,
  ...rest
}: { name: string; className?: string } & React.HTMLAttributes<HTMLSpanElement>) {
  if (hasVendorLogo(name)) {
    return <VendorLogo name={name} className={className} />
  }

  return (
    <span
      {...rest}
      className={cn(
        "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-secondary text-[9px] font-bold uppercase",
        toneFor(name),
        className,
      )}
    >
      {connectorLabel(name).slice(0, 1)}
    </span>
  )
}

/**
 * A connector chip: monogram + name. Used in the popup's always-visible
 * connection status (Part A.2) so "which connectors are active" is glanceable
 * rather than a comma-joined string.
 */
export function ConnectorChip({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card py-0.5 pl-0.5 pr-2">
      <ConnectorIcon name={name} aria-hidden="true" />
      <span className="text-[11px] font-medium text-foreground">
        {connectorLabel(name)}
      </span>
    </span>
  )
}

/**
 * The vendor a catalog action belongs to. Action ids are namespaced
 * `vendor.object.verb`, so the vendor is the first segment — shown plainly in
 * the approval card because "where is this write going" is the single most
 * important thing to get across (Part C.2).
 */
export function vendorOf(invokeAction: string): string {
  const first = String(invokeAction || "").split(".")[0]
  // Shares connectorLabel so the approval card says "HubSpot", not "Hubspot".
  return first ? connectorLabel(first) : "Connector"
}
