"use client"

/**
 * Optional GSAP ScrollTrigger prototype for the department network.
 * Compared against Motion autoplay: Motion wins for Nodus calmness on About
 * (no over-pinning). Keep this export for experiments / future sticky pages.
 */

import { useEffect, useRef, useState } from "react"
import gsap from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { useReducedMotion } from "framer-motion"
import { GravitreDepartmentNetwork } from "./department-network"
import { cn } from "@/lib/utils"

const SCROLL_CAPTIONS = [
  "Network resolves.",
  "Sales creates a signal.",
  "Gravitre connects the context.",
  "Support receives what it needs.",
  "Finance and Ops coordinate.",
  "Outcomes return.",
  "Shared intelligence learns.",
] as const

export function GravitreDepartmentNetworkScroll({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const pinRef = useRef<HTMLDivElement>(null)
  const [captionIdx, setCaptionIdx] = useState(0)

  useEffect(() => {
    if (reduce || typeof window === "undefined") return
    const pin = pinRef.current
    if (!pin) return
    gsap.registerPlugin(ScrollTrigger)
    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: pin,
        start: "top 20%",
        end: "+=90%",
        scrub: 0.6,
        onUpdate: (self) => {
          const i = Math.min(
            SCROLL_CAPTIONS.length - 1,
            Math.floor(self.progress * SCROLL_CAPTIONS.length),
          )
          setCaptionIdx(i)
        },
      })
    }, pin)
    return () => ctx.revert()
  }, [reduce])

  return (
    <div ref={pinRef} className={cn("relative", className)}>
      <GravitreDepartmentNetwork autoplay={!reduce} />
      {!reduce ? (
        <p className="mt-2 text-center text-xs font-medium text-[color:var(--g-text-muted)]">
          {SCROLL_CAPTIONS[captionIdx]}
        </p>
      ) : null}
    </div>
  )
}
