import { useState } from "react"
import { Check, Copy } from "lucide-react"

import { ConnectorIcon, connectorLabel } from "@/components/connector-icon"
import { Badge, SectionLabel } from "@/components/ui"
import { cn } from "@/lib/cn"
import { connectorOf } from "@/lib/params"
import type { EnrichMatch, Extracted } from "@/lib/types"

/**
 * Copy button for a single value. Enrichment output exists to be pasted
 * somewhere else, so copy is the highest-frequency action on this panel.
 */
function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)

  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1400)
        })
      }}
      // Only revealed on hover/focus so the resting state stays calm, but it is
      // always reachable by keyboard.
      className={cn(
        "shrink-0 rounded-md p-1 text-muted-foreground opacity-0 transition",
        "hover:bg-secondary hover:text-foreground focus-visible:opacity-100",
        "outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "group-hover:opacity-100",
        copied && "opacity-100 text-success",
      )}
      aria-label={copied ? `${label} copied` : `Copy ${label.toLowerCase()}`}
    >
      {copied ? (
        <Check aria-hidden="true" className="h-3 w-3" />
      ) : (
        <Copy aria-hidden="true" className="h-3 w-3" />
      )}
    </button>
  )
}

const FIELD_ORDER: Array<{ key: keyof Extracted; label: string }> = [
  { key: "fullName", label: "Name" },
  { key: "title", label: "Title" },
  { key: "company", label: "Company" },
  // Returned for company sites, where it is often the only identity field.
  { key: "domain", label: "Domain" },
  { key: "email", label: "Email" },
]

export function ExtractedFields({ extracted }: { extracted: Extracted }) {
  const rows = FIELD_ORDER.map(({ key, label }) => ({
    label,
    value: extracted[key],
  })).filter((r): r is { label: string; value: string } => Boolean(r.value))

  if (!rows.length) return null

  return (
    <div>
      <SectionLabel>Read from this page</SectionLabel>
      <dl className="mt-1.5 flex flex-col gap-px overflow-hidden rounded-lg border border-border">
        {rows.map(({ label, value }) => (
          <div
            key={label}
            className="group flex items-start gap-2 border-b border-border bg-card px-2.5 py-2 last:border-b-0"
          >
            <dt className="w-[68px] shrink-0 pt-px text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </dt>
            <dd
              className={cn(
                "min-w-0 flex-1 text-[13px] leading-snug text-foreground",
                // Emails are long and must not be silently clipped, so wrap
                // rather than truncate.
                label === "Email" && "break-all font-mono text-[12px]",
              )}
            >
              {value}
            </dd>
            <CopyButton value={value} label={label} />
          </div>
        ))}
      </dl>
    </div>
  )
}

export function MatchList({ matches }: { matches: EnrichMatch[] }) {
  if (!matches.length) return null

  return (
    <div>
      <SectionLabel>Connector lookups</SectionLabel>
      <ul className="mt-1.5 flex flex-col gap-1.5">
        {matches.map((match) => {
          const connector = connectorOf(match.action)
          return (
            <li
              key={match.action}
              className="flex items-start gap-2 rounded-lg border border-border bg-card px-2.5 py-2"
            >
              <ConnectorIcon
                name={connector}
                className="mt-px h-4 w-4 shrink-0"
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-[12px] font-medium text-foreground">
                    {connectorLabel(connector)}
                  </span>
                  <Badge tone={match.success ? "success" : "warning"}>
                    {match.confidenceLabel || (match.success ? "matched" : "no match")}
                  </Badge>
                </div>
                {/* The action id is the audit trail — keep it visible but quiet. */}
                <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
                  {match.action}
                </p>
                {match.error && (
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {match.error}
                  </p>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
