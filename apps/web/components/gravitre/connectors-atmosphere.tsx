"use client"

/**
 * Connectors canvas field — same daylight 10px dot grid as the Nodus homepage
 * Agentic Intelligence / Benefits sections.
 */

import { cn } from "@/lib/utils"

export function ConnectorsAtmosphere({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden bg-white", className)}
      data-connectors-atmosphere=""
    >
      <div className="pointer-events-none absolute inset-0 h-full w-full bg-[radial-gradient(var(--color-dots)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]" />
    </div>
  )
}
