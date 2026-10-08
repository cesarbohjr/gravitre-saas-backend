"use client"

import { cn } from "@/lib/utils"

export function GravitreEvidenceMark({
  label,
  tone = "evidence",
}: {
  label: string
  tone?: "evidence" | "error" | "waiting"
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold",
        tone === "evidence" &&
          "border-[color:color-mix(in_oklch,var(--g-intelligence)_35%,var(--line))] bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]",
        tone === "error" && "border-destructive/30 bg-destructive/10 text-danger-text",
        tone === "waiting" && "border-warning/30 bg-warning/10 text-warning-text",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-sm",
          tone === "evidence" && "bg-[color:var(--g-intelligence)]",
          tone === "error" && "bg-destructive",
          tone === "waiting" && "bg-warning",
        )}
        aria-hidden
      />
      {label}
    </span>
  )
}
