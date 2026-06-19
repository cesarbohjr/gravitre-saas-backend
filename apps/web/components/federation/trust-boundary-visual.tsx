"use client"

import { motion, useReducedMotion } from "framer-motion"
import { Building2, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Two-org trust boundary: your org and a partner org sit on either side of a
 * mutual-consent gate. Teaches the core federation rule — nothing crosses the
 * boundary until both sides consent — in a single hero visual, replacing the
 * repeated generic handshake icon.
 */
export function TrustBoundaryVisual({ className }: { className?: string }) {
  const reduced = useReducedMotion()

  return (
    <div className={cn("mx-auto w-full max-w-md", className)} aria-hidden>
      <div className="flex items-center justify-center gap-3 sm:gap-4">
        {/* Your org */}
        <OrgNode label="Your org" tone="primary" />

        {/* Consent gate + animated cross-boundary flow */}
        <div className="relative flex flex-1 flex-col items-center">
          <div className="relative h-px w-full bg-gradient-to-r from-primary/40 via-border to-info/40">
            {!reduced && (
              <motion.span
                className="absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-primary"
                initial={{ left: "0%", opacity: 0 }}
                animate={{ left: ["0%", "44%"], opacity: [0, 1, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
              />
            )}
            {!reduced && (
              <motion.span
                className="absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-info"
                initial={{ right: "0%", opacity: 0 }}
                animate={{ right: ["0%", "44%"], opacity: [0, 1, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut", delay: 1.1 }}
              />
            )}
          </div>
          <div className="-mt-[14px] flex h-7 w-7 items-center justify-center rounded-full border border-border bg-card shadow-sm">
            <ShieldCheck className="h-4 w-4 text-success" />
          </div>
          <span className="mt-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            Consent
          </span>
        </div>

        {/* Partner org */}
        <OrgNode label="Partner org" tone="info" />
      </div>
    </div>
  )
}

function OrgNode({ label, tone }: { label: string; tone: "primary" | "info" }) {
  const ring = tone === "primary" ? "border-primary/30 bg-primary/10" : "border-info/30 bg-info/10"
  const text = tone === "primary" ? "text-primary" : "text-info"
  return (
    <div className="flex shrink-0 flex-col items-center gap-1.5">
      <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl border", ring)}>
        <Building2 className={cn("h-5 w-5", text)} />
      </div>
      <span className="text-[11px] font-medium text-foreground">{label}</span>
    </div>
  )
}
