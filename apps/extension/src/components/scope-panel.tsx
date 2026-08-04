import { useMemo, useState } from "react"
import { ChevronDown, ShieldCheck } from "lucide-react"

import { cn } from "@/lib/cn"
import { Badge, Divider, SectionLabel } from "./ui"

/**
 * "Here's exactly what this can see" (Part A.3).
 *
 * The host list is read from the live manifest at runtime rather than written
 * out by hand, so this disclosure cannot drift from the permissions Chrome has
 * actually granted. That honesty is the whole value of the affordance: a
 * hardcoded list would be marketing copy, this is the real grant.
 */

/** Turn "https://mail.google.com/*" into "mail.google.com". */
function prettyHost(pattern: string): string {
  return pattern
    .replace(/^\*:\/\//, "")
    .replace(/^https?:\/\//, "")
    .replace(/\/\*$/, "")
    // "*.linkedin.com" and "www.linkedin.com" are the same site to a reader;
    // collapse both so the list stays scannable rather than listing near-dupes.
    .replace(/^\*\./, "")
    .replace(/^www\./, "")
}

/** Gravitre's own origins are plumbing, not a page the user is browsing. */
const OWN_ORIGIN = /gravitre|railway\.app|vercel\.app|localhost/i

export function ScopePanel({
  allowedActionCount,
  defaultOpen = false,
  className,
}: {
  allowedActionCount?: number
  defaultOpen?: boolean
  className?: string
}) {
  const [open, setOpen] = useState(defaultOpen)

  const { pageHosts, permissions } = useMemo(() => {
    // Guard: the harness renders this outside a real extension context.
    const manifest =
      typeof chrome !== "undefined" && chrome.runtime?.getManifest
        ? chrome.runtime.getManifest()
        : undefined
    const raw = (manifest?.host_permissions ?? []) as unknown[]
    const hosts = raw.filter((h): h is string => typeof h === "string").map(prettyHost)
    const unique = Array.from(new Set(hosts))
    const perms = (manifest?.permissions ?? []) as unknown[]
    return {
      pageHosts: unique.filter((h) => !OWN_ORIGIN.test(h)),
      permissions: perms.filter((p): p is string => typeof p === "string"),
    }
  }, [])

  const readsActiveTabOnly = permissions.includes("activeTab")

  return (
    <div className={cn("rounded-lg border border-border bg-secondary/40", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cn(
          "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left",
          "outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <ShieldCheck aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-success" />
        <span className="flex-1 text-[12px] font-medium text-foreground">
          What Gravitre can see
        </span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-150",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="gvt-animate-row px-2.5 pb-2.5">
          <Divider className="mb-2.5" />

          <SectionLabel>Only these sites</SectionLabel>
          <ul className="mt-1.5 flex flex-wrap gap-1">
            {pageHosts.map((host) => (
              <li key={host}>
                <Badge tone="neutral" className="font-mono">
                  {host}
                </Badge>
              </li>
            ))}
          </ul>

          <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
            {readsActiveTabOnly
              ? "Nothing is read until you open the overlay, and only on the tab you are looking at."
              : "Page content is read only when you open the overlay."}{" "}
            Gravitre never reads other tabs, and never writes anywhere without your
            explicit approval.
          </p>

          {typeof allowedActionCount === "number" && allowedActionCount > 0 && (
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              Writes are limited to{" "}
              <span className="font-medium text-foreground">
                {allowedActionCount} approved
              </span>{" "}
              catalog {allowedActionCount === 1 ? "action" : "actions"}, each gated by
              your approval.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
