"use client"

import React from "react"
import MeshGradient from "@/components/marketing/nodus/mesh-gradient"

/**
 * Nodus auth side panel — Gravitre copy only (no invented testimonials).
 */
export function AuthIllustration() {
  return (
    <div className="relative flex min-h-80 flex-col items-start justify-end overflow-hidden rounded-2xl bg-foreground p-4 md:min-h-[28rem] md:p-8">
      <div className="relative z-40 mb-2 flex flex-wrap items-center gap-2">
        <p className="rounded-md bg-foreground/50 px-2 py-1 text-xs text-background">Agents</p>
        <p className="rounded-md bg-foreground/50 px-2 py-1 text-xs text-background">Workflows</p>
        <p className="rounded-md bg-foreground/50 px-2 py-1 text-xs text-background">Approvals</p>
      </div>
      <div className="relative z-40 max-w-sm rounded-xl bg-foreground/50 p-4 backdrop-blur-sm">
        <h2 className="text-lg font-medium text-background md:text-xl">
          One AI brain for your entire business.
        </h2>
        <p className="mt-4 text-sm text-background/60">
          Connect tools, coordinate agents and people, measure outcomes, and improve
          with human approval where it matters.
        </p>
      </div>

      <div className="absolute -top-48 -right-40 z-20 grid rotate-45 transform grid-cols-4 gap-32 mask-r-from-50%">
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
      </div>

      <div className="absolute top-0 -right-10 z-20 grid rotate-45 transform grid-cols-4 gap-32 mask-r-from-50% opacity-50">
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
        <div className="size-40 shrink-0 rounded-3xl bg-background/5 shadow-[0px_2px_0px_0px_var(--muted-foreground)_inset]" />
      </div>
      <MeshGradient className="absolute inset-0 z-30 h-full w-200 mask-t-from-50% blur-3xl" />
    </div>
  )
}
