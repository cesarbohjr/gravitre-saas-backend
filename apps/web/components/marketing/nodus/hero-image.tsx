import React from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"
import { Container } from "./container"

/** Static corner markers — avoids client Dot (mousemove + framer-motion) on LCP path. */
function CornerDot({ className }: { className?: string }) {
  return (
    <div
      className={cn("absolute z-10 h-2 w-2 bg-[color:var(--color-primary)]", className)}
      aria-hidden
    />
  )
}

/**
 * Hero product screenshot — server-rendered for Lighthouse LCP.
 * Parallax / interactive dots removed from the critical path (see bfd7a000).
 */
export const HeroImage = () => {
  return (
    <Container className="border-divide relative flex items-start justify-start overflow-hidden border-x bg-gray-100 p-2 perspective-distant md:p-4 lg:p-8 dark:bg-neutral-800">
      <CornerDot className="top-0 left-0 xl:-top-1 xl:-left-2" />
      <CornerDot className="top-0 right-0 xl:-top-1 xl:-right-2" />
      <CornerDot className="bottom-0 left-0 xl:-bottom-1 xl:-left-2" />
      <CornerDot className="bottom-0 right-0 xl:-bottom-1 xl:-right-2" />
      <div className="relative w-full">
        <div className="relative z-10 h-full w-full">
          <Image
            src="/nodus/dashboard@3x.png"
            alt="Gravitre product preview"
            className="w-full"
            priority
            fetchPriority="high"
            sizes="(max-width: 1024px) 100vw, min(100vw, 1280px)"
            width={1000}
            height={1000}
            draggable={false}
          />
        </div>
        <div className="absolute inset-0 z-0 m-auto h-[90%] w-[95%] rounded-lg border border-(--pattern-fg) bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px] bg-fixed" />
      </div>
    </Container>
  )
}
