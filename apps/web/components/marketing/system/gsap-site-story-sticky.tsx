"use client"

/**
 * Marketing System 4.0 — pinned GSAP sticky narrative (Connect → Learn).
 * Used on /roadmap. Honors prefers-reduced-motion (static grid fallback).
 * No TRAINED badges, prices, or entitlement claims.
 */

import { useEffect, useRef, useState } from "react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { useReducedMotion } from "framer-motion"
import { GravitreSection, GravitreSectionHeader } from "@/components/marketing/system/section"
import { cn } from "@/lib/utils"

export const SITE_STORY_STAGES = [
  {
    id: "connect",
    label: "Connect",
    blurb: "Link the tools and data your team already uses — governed connectors, not one-off scripts.",
  },
  {
    id: "understand",
    label: "Understand",
    blurb: "Gravitre reads context across systems so agents know what matters before they act.",
  },
  {
    id: "coordinate",
    label: "Coordinate",
    blurb: "Agents and workflows share governed context — coordinated work, not orphan automations.",
  },
  {
    id: "act",
    label: "Act",
    blurb: "Writes and external actions pass through approval gates you control.",
  },
  {
    id: "verify",
    label: "Verify",
    blurb: "Outcomes, audit trails, and operator review close the loop on every run.",
  },
  {
    id: "learn",
    label: "Learn",
    blurb: "GIBE learns from approved outcomes — org memory that compounds over time.",
  },
] as const

export function GsapSiteStorySticky({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const pinRef = useRef<HTMLDivElement>(null)
  const panelRefs = useRef<(HTMLDivElement | null)[]>([])
  const pillRefs = useRef<(HTMLButtonElement | null)[]>([])
  const [active, setActive] = useState(0)
  // Defer reduced-motion branch until after mount so SSR HTML matches first paint.
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])
  const reduce = mounted && !!reducePreference

  useEffect(() => {
    if (reduce || typeof window === "undefined") return
    const pin = pinRef.current
    if (!pin) return

    gsap.registerPlugin(ScrollTrigger)

    const ctx = gsap.context(() => {
      const panels = panelRefs.current.filter(Boolean) as HTMLDivElement[]
      const pills = pillRefs.current.filter(Boolean) as HTMLButtonElement[]
      const n = SITE_STORY_STAGES.length

      gsap.set(panels, { autoAlpha: 0, y: 16 })
      gsap.set(panels[0], { autoAlpha: 1, y: 0 })
      gsap.set(pills, { opacity: 0.45, scale: 0.98 })
      gsap.set(pills[0], { opacity: 1, scale: 1 })

      ScrollTrigger.create({
        trigger: pin,
        start: "top top+=72",
        end: () => `+=${Math.round(n * window.innerHeight * 0.65)}`,
        pin: true,
        pinSpacing: true,
        scrub: 0.5,
        anticipatePin: 1,
        onUpdate: (self) => {
          const idx = Math.min(Math.floor(self.progress * n), n - 1)
          setActive(idx)
          panels.forEach((el, i) => {
            gsap.to(el, {
              autoAlpha: i === idx ? 1 : 0,
              y: i === idx ? 0 : i < idx ? -12 : 12,
              duration: 0.3,
              overwrite: "auto",
              ease: "power2.out",
            })
          })
          pills.forEach((el, i) => {
            gsap.to(el, {
              opacity: i === idx ? 1 : 0.45,
              scale: i === idx ? 1 : 0.98,
              duration: 0.2,
              overwrite: "auto",
            })
          })
        },
      })
    }, pin)

    return () => {
      ctx.revert()
    }
  }, [reduce])

  if (reduce) {
    return (
      <GravitreSection className={className}>
        <GravitreSectionHeader
          badge="Product spine"
          title="Connect → Learn"
          description="How Gravitre moves from connected systems to governed outcomes and org learning."
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SITE_STORY_STAGES.map((stage) => (
            <div key={stage.id} className="rounded-xl border border-divide bg-gray-50 p-5">
              <p className="text-sm font-medium text-brand">{stage.label}</p>
              <p className="mt-2 text-sm text-muted-foreground">{stage.blurb}</p>
            </div>
          ))}
        </div>
      </GravitreSection>
    )
  }

  return (
    <div
      ref={pinRef}
      className={cn("relative flex min-h-[70vh] items-center py-12", className)}
      data-marketing-gsap-story=""
    >
      <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] md:px-8">
        <div className="flex flex-col justify-center gap-2" role="tablist" aria-label="Site story stages">
          {SITE_STORY_STAGES.map((stage, i) => (
            <button
              key={stage.id}
              type="button"
              role="tab"
              aria-selected={active === i}
              ref={(el) => {
                pillRefs.current[i] = el
              }}
              className="flex items-center gap-3 rounded-lg border border-divide bg-white px-4 py-2.5 text-left"
            >
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  i === SITE_STORY_STAGES.length - 1
                    ? "bg-primary"
                    : "bg-[color:var(--g-intelligence)]"
                }`}
              />
              <span className="text-sm font-medium text-foreground">{stage.label}</span>
            </button>
          ))}
        </div>
        <div className="relative min-h-[200px]" aria-live="polite">
          {SITE_STORY_STAGES.map((stage, i) => (
            <div
              key={stage.id}
              ref={(el) => {
                panelRefs.current[i] = el
              }}
              className="absolute inset-0 flex flex-col justify-center"
            >
              <p className="text-sm font-medium uppercase tracking-wide text-brand">{stage.label}</p>
              <p className="mt-3 max-w-lg text-2xl font-semibold text-foreground md:text-3xl">{stage.blurb}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
