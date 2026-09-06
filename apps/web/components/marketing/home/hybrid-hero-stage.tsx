"use client"

/**
 * Hybrid A+B hero stage — UI 3.0 Phase 3.
 * A: layered product captures as stage content.
 * B: living Intent → Tool → Approval → Verified choreography.
 * Real /public/product screens only — no fabricated dashboards or ROI.
 */

import { AnimatePresence, motion } from "framer-motion"
import { useEffect, useState } from "react"
import { useMotionPrefs } from "@/lib/animations"
import {
  ProductStage,
  type ProductStageBeat,
} from "@/components/gravitre/visual"
import { cn } from "@/lib/utils"

type StageShot = {
  beat: ProductStageBeat
  src: string
  chrome: string
  alt: string
  ms: number
}

const SEQUENCE: StageShot[] = [
  {
    beat: "intent",
    src: "/product/app-ai.png",
    chrome: "gravitre.app/ai",
    alt: "Gravitre chat intent",
    ms: 1600,
  },
  {
    beat: "tool",
    src: "/product/app-connectors.png",
    chrome: "gravitre.app/connectors",
    alt: "Gravitre connectors tool path",
    ms: 1700,
  },
  {
    beat: "approval",
    src: "/product/app-approvals.png",
    chrome: "gravitre.app/approvals",
    alt: "Gravitre approval gate",
    ms: 1800,
  },
  {
    beat: "verified",
    src: "/product/app-activity.png",
    chrome: "gravitre.app/activity",
    alt: "Gravitre verified run activity",
    ms: 1700,
  },
  {
    beat: "idle",
    src: "/product/app-workflows.png",
    chrome: "gravitre.app/workflows",
    alt: "Gravitre workflows ready",
    ms: 2200,
  },
]

const LAYER_SHOTS = [
  { src: "/product/app-ai.png", label: "Chat", className: "z-[3] translate-y-0" },
  { src: "/product/app-agents.png", label: "Agents", className: "z-[2] translate-y-3 opacity-95" },
  { src: "/product/app-approvals.png", label: "Approvals", className: "z-[1] translate-y-6 opacity-90" },
] as const

export function HybridHeroStage({ className }: { className?: string }) {
  const { reduced } = useMotionPrefs()
  const [index, setIndex] = useState(0)
  const shot = SEQUENCE[reduced ? SEQUENCE.length - 1 : index] ?? SEQUENCE[0]

  useEffect(() => {
    if (reduced) return
    const ms = SEQUENCE[index]?.ms ?? 1800
    const timer = window.setTimeout(() => {
      setIndex((i) => (i + 1) % SEQUENCE.length)
    }, ms)
    return () => window.clearTimeout(timer)
  }, [index, reduced])

  return (
    <div className={cn("relative w-full", className)}>
      {/* A — layered product silhouette behind living stage */}
      <div
        className="pointer-events-none absolute -right-4 top-8 hidden w-[42%] max-w-sm lg:block"
        aria-hidden
      >
        <div className="relative h-48">
          {LAYER_SHOTS.map((layer) => (
            <div
              key={layer.label}
              className={cn(
                "absolute inset-x-0 overflow-hidden rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] shadow-[var(--g-shadow-elevated)]",
                layer.className,
              )}
              style={{ boxShadow: "var(--g-highlight-top), var(--g-shadow-elevated)" }}
            >
              <div className="relative aspect-[16/10] w-full">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={layer.src}
                  alt=""
                  className="h-full w-full object-cover object-top"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <ProductStage
        composition="living"
        beat={shot.beat}
        chromeLabel={shot.chrome}
        showTrace
        caption="Illustrative product sequence — fixture captures, not live customer metrics"
        className="relative z-[4]"
      >
        <div className="relative overflow-hidden rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-3)]">
          <div className="relative w-full" style={{ aspectRatio: "16 / 10", minHeight: 200 }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={shot.src + shot.beat}
                className="absolute inset-0 flex items-start justify-center"
                initial={reduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduced ? undefined : { opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- marketing stage cycle */}
                <img
                  src={shot.src}
                  alt={shot.alt}
                  className="h-full w-full object-cover object-left-top"
                  loading="eager"
                  decoding="async"
                />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </ProductStage>
    </div>
  )
}
