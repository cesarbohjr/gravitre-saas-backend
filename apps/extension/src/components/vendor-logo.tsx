import { cn } from "@/lib/cn"

/**
 * Official vendor marks for connector icons.
 *
 * The extension previously drew tinted monograms here, on the reasoning that
 * tracing logos was both a licensing question and inconsistent with the app's
 * Lucide set. Two things changed that: the monograms made every connector look
 * the same at a glance ("H", "A", "S", "S"), and the marks are now vendored
 * from theSVG rather than traced by hand.
 *
 * Every mark comes from ONE source so the scheme is uniform across the popup,
 * side panel and overlay — no mixing of full-colour logos with monochrome
 * glyphs and letters.
 *
 * The SVGs are inlined into the bundle (not loaded as files) because the overlay
 * is a content script on a third-party page: a root-relative path would resolve
 * against the host site, and an extension asset URL would need
 * web_accessible_resources and could still be refused by the host page's CSP.
 *
 * Marks are stored and rendered exactly as published — never recoloured or
 * redrawn — and identify genuine integrations. Trademarks belong to their
 * respective owners.
 */

// Eagerly inlined at build time; `?raw` gives us the markup as a string.
const RAW = import.meta.glob<string>("../assets/vendor-logos/*.svg", {
  query: "?raw",
  import: "default",
  eager: true,
})

/**
 * Drops width/height off the root <svg> so the tile controls the size. Without
 * this, a mark published at 128px would blow out the layout.
 */
function fluid(svg: string): string {
  return svg.replace(/<svg\b[^>]*>/i, (tag) =>
    tag.replace(/\s(?:width|height)="[^"]*"/gi, ""),
  )
}

const LOGOS: Record<string, string> = {}
for (const [path, svg] of Object.entries(RAW)) {
  const key = path.split("/").pop()?.replace(/\.svg$/, "")
  if (key && typeof svg === "string") LOGOS[key] = fluid(svg)
}

/**
 * Connector ids arrive in several shapes — `hubspot`, `HubSpot`,
 * `microsoft_365`, or an action namespace like `hubspot.contact.create` — so
 * match on a normalised substring.
 *
 * Order matters: `gmail` must be tested before `google`, and `outlook` before
 * `microsoft`, or the broader brand would swallow the specific product.
 */
const ALIASES: Array<[RegExp, string]> = [
  [/hubspot/, "hubspot"],
  [/apollo/, "apollo"],
  [/salesforce|sfdc/, "salesforce"],
  [/slack/, "slack"],
  [/linkedin/, "linkedin"],
  [/gmail/, "gmail"],
  [/outlook/, "outlook"],
  [/microsoft|m365|office365/, "microsoft365"],
  [/google/, "google"],
  [/notion/, "notion"],
  [/pipedrive/, "pipedrive"],
  [/zendesk/, "zendesk"],
  [/intercom/, "intercom"],
  [/stripe/, "stripe"],
  [/jira/, "jira"],
  [/asana/, "asana"],
  [/github/, "github"],
]

export function vendorKeyFor(name: string): string | undefined {
  const key = String(name || "").toLowerCase().replace(/[^a-z0-9]/g, "")
  if (!key) return undefined
  for (const [pattern, vendor] of ALIASES) {
    if (pattern.test(key)) return vendor
  }
  return undefined
}

export function hasVendorLogo(name: string): boolean {
  const key = vendorKeyFor(name)
  return Boolean(key && LOGOS[key])
}

/**
 * The official mark on a light tile.
 *
 * The tile is not decoration: brand marks are fixed colours we cannot alter,
 * and GitHub, Notion and Zendesk are near-black, so they vanish against a dark
 * panel. A tile that stays light in both themes keeps every mark legible and
 * presents all vendors identically.
 */
export function VendorLogo({
  name,
  className,
}: {
  name: string
  className?: string
}) {
  const key = vendorKeyFor(name)
  const svg = key ? LOGOS[key] : undefined
  if (!svg) return null

  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-flex h-4 w-4 shrink-0 items-center justify-center overflow-hidden rounded-[4px] border border-vendor-surface-border bg-vendor-surface p-[1.5px]",
        "[&>svg]:h-full [&>svg]:w-full [&>svg]:object-contain",
        className,
      )}
      // Static, build-time assets from our own repo; no user input reaches this.
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
