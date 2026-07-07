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
      className={cn(boxClass, "bg-muted/70 text-muted-foreground font-semibold tracking-tight")}
      aria-label={name}
    >
      <span aria-hidden>{orgInitials(name)}</span>
    </div>
  )
}
