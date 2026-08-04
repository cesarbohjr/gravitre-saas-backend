import { Building2, Linkedin, Mail, Slack, Cloud } from "lucide-react"

import { cn } from "@/lib/cn"
import type { Surface } from "@/lib/types"

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
 * A connector chip: monogram + name. Used in the popup's always-visible
 * connection status (Part A.2) so "which connectors are active" is glanceable
 * rather than a comma-joined string.
 */
export function ConnectorChip({ name }: { name: string }) {
  const label = name.replace(/[_-]/g, " ")
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card py-0.5 pl-0.5 pr-2">
      <span
        aria-hidden="true"
        className={cn(
          "inline-flex h-4 w-4 items-center justify-center rounded-full bg-secondary text-[9px] font-bold uppercase",
          toneFor(name),
        )}
      >
        {label.slice(0, 1)}
      </span>
      <span className="text-[11px] font-medium capitalize text-foreground">{label}</span>
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
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : "Connector"
}
