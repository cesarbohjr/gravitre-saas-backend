"use client"

import Image from "next/image"
import { cn } from "@/lib/utils"

/** Sidebar-style organization section icon (org chart / hierarchy). */
export function OrganizationSectionIcon({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-border/70 bg-secondary/80",
        className,
      )}
    >
      <svg
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
        className="h-3.5 w-3.5 text-muted-foreground"
      >
        <rect x="5.5" y="1.5" width="5" height="3" rx="0.75" stroke="currentColor" strokeWidth="1.25" />
        <path d="M8 4.5V7" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
        <path d="M4 7H12" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
        <path d="M4 7V8.5M12 7V8.5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
        <rect x="1.5" y="8.5" width="5" height="3" rx="0.75" stroke="currentColor" strokeWidth="1.25" />
        <rect x="9.5" y="8.5" width="5" height="3" rx="0.75" stroke="currentColor" strokeWidth="1.25" />
      </svg>
    </span>
  )
}

const sizeClasses = {
  xs: "h-5 w-5 rounded-md text-[9px]",
  sm: "h-6 w-6 rounded-md text-[10px]",
  md: "h-8 w-8 rounded-lg text-xs",
  lg: "h-14 w-14 rounded-xl text-lg",
} as const

function orgInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return "?"
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
}

// Brand-aligned gradient palette for per-org monograms. The lead entry is
// Gravitre's emerald so the workspace family reads as on-brand, with a small
// set of complementary hues (shared with the department color language) to
// give each organization a distinct, recognizable identity.
const ORG_GRADIENTS = [
  "from-emerald-500 to-teal-600",
  "from-teal-500 to-cyan-600",
  "from-blue-500 to-indigo-600",
  "from-violet-500 to-fuchsia-600",
  "from-amber-500 to-orange-600",
  "from-rose-500 to-pink-600",
] as const

/**
 * Stable hash so a given org name always maps to the same brand gradient.
 * Uses FNV-1a, which distributes short, similar strings (org names) far more
 * evenly than a simple polynomial hash — avoiding collisions where two
 * different orgs would otherwise share the same color.
 */
function orgGradient(name: string): string {
  const key = name.trim().toLowerCase()
  let hash = 0x811c9dc5 // FNV offset basis
  for (let i = 0; i < key.length; i += 1) {
    hash ^= key.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0 // FNV prime
  }
  return ORG_GRADIENTS[hash % ORG_GRADIENTS.length]
}

/**
 * Per-organization branded monogram — a rounded gradient tile with the org's
 * initials. Deterministic color keeps each workspace visually distinct while
 * staying inside the Gravitre brand palette. Used in the org switcher and as
 * the fallback for organizations without an uploaded logo.
 */
export function OrgMonogram({
  name,
  size = "xs",
  className,
}: {
  name: string
  size?: keyof typeof sizeClasses
  className?: string
}) {
  return (
    <span
      role="img"
      aria-label={name}
      className={cn(
        "flex shrink-0 items-center justify-center bg-gradient-to-br font-semibold uppercase leading-none tracking-tight text-white shadow-sm ring-1 ring-black/10 dark:ring-white/15",
        orgGradient(name),
        sizeClasses[size],
        className,
      )}
    >
      <span aria-hidden>{orgInitials(name)}</span>
    </span>
  )
}

export function OrganizationLogoAvatar({
  name,
  logoUrl,
  size = "sm",
  className,
}: {
  name: string
  logoUrl?: string | null
  size?: keyof typeof sizeClasses
  className?: string
}) {
  const resolvedLogo = (logoUrl || "").trim()
  const boxClass = cn(
    "relative flex shrink-0 items-center justify-center overflow-hidden border border-border bg-secondary",
    sizeClasses[size],
    className,
  )

  if (resolvedLogo.startsWith("data:") || resolvedLogo.startsWith("http")) {
    return (
      <div className={boxClass}>
        {resolvedLogo.startsWith("data:") ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={resolvedLogo} alt="" className="h-full w-full object-cover" />
        ) : (
          <Image src={resolvedLogo} alt="" fill className="object-cover" sizes="56px" unoptimized />
        )}
      </div>
    )
  }

  return (
    <div
      className={cn(
        boxClass,
        "border-transparent bg-gradient-to-br font-semibold uppercase tracking-tight text-white shadow-sm ring-1 ring-black/10 dark:ring-white/15",
        orgGradient(name),
      )}
      role="img"
      aria-label={name}
    >
      <span aria-hidden>{orgInitials(name)}</span>
    </div>
  )
}
