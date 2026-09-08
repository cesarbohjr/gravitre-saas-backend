"use client"

/**
 * Persistent secondary AI Helper — opens a restrained workspace sheet.
 * Hidden on /ai (full workspace). Not a dominant dashboard CTA.
 */

import { useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

const QUICK_PROMPTS = [
  { label: "Summarize pending approvals", prompt: "Summarize my pending approvals and what needs a decision." },
  { label: "Agent status overview", prompt: "Give me a brief status of my agents and anything failing." },
  { label: "Recent run failures", prompt: "What workflow runs failed recently and why?" },
  { label: "Connector health", prompt: "Which connectors need attention right now?" },
] as const

export function FloatingAiWorkspace() {
  const pathname = usePathname()
  const router = useRouter()
  const [open, setOpen] = useState(false)

  const onAiRoute = pathname === "/ai" || pathname.startsWith("/ai/")
  if (onAiRoute) return null

  const openFull = (prompt?: string) => {
    setOpen(false)
    const href = prompt
      ? `${APP_ROUTES.gravitreAi}?prompt=${encodeURIComponent(prompt)}`
      : APP_ROUTES.gravitreAi
    router.push(href)
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "fixed bottom-20 right-4 z-40 flex h-11 w-11 items-center justify-center rounded-[var(--np-radius-lg)]",
          "border border-divide bg-[color:var(--g-surface-1)] text-[color:var(--g-brand)] shadow-[var(--np-shadow)]",
          "transition-colors hover:bg-[color:var(--g-surface-2)] md:bottom-6 md:right-6",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
        )}
        aria-label="Open Gravitre AI helper"
      >
        <NucleoAgent className="h-5 w-5" />
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="right"
          className="flex w-full flex-col gap-0 border-divide p-0 sm:max-w-md"
        >
          <SheetHeader className="border-b border-divide px-4 py-3 pr-12 text-left">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
                <NucleoAgent className="h-4 w-4" />
              </div>
              <div>
                <SheetTitle className={TYPE.sectionTitle}>Gravitre AI</SheetTitle>
                <SheetDescription className={TYPE.meta}>
                  Quick helper. Opens the full AI workspace for chat, tools, and voice.
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            <div>
              <p className={cn(TYPE.eyebrow, "mb-2")}>Quick prompts</p>
              <ul className="space-y-1.5">
                {QUICK_PROMPTS.map((item) => (
                  <li key={item.label}>
                    <button
                      type="button"
                      onClick={() => openFull(item.prompt)}
                      className={cn(
                        "w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] px-3 py-2.5 text-left text-sm",
                        "transition-colors hover:bg-[color:var(--g-surface-2)]",
                      )}
                    >
                      {item.label}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <p className={TYPE.meta}>
              Continues in the authenticated AI workspace with your org context, connectors, and
              approval gates unchanged.
            </p>
          </div>

          <div className="border-t border-divide p-4">
            <Button type="button" className="w-full" onClick={() => openFull()}>
              Open full AI workspace
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
