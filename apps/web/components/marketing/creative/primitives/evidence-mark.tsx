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
          "border-[color:color-mix(in_oklch,var(--g-intelligence)_35%,#eaedf1)] bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]",
        tone === "error" && "border-red-200 bg-red-50 text-red-700",
        tone === "waiting" && "border-amber-200 bg-amber-50 text-amber-800",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-sm",
          tone === "evidence" && "bg-[color:var(--g-intelligence)]",
          tone === "error" && "bg-red-500",
          tone === "waiting" && "bg-amber-500",
        )}
        aria-hidden
      />
      {label}
    </span>
  )
}
