import React from "react"
import Image from "next/image"
import { Container } from "./container"
import { Dot } from "./common/dots"

/**
 * Hero product screenshot — server-rendered for crisp marketing display.
 * Uses the full-resolution dashboard capture in public/nodus/.
 *
 * The corner `Dot`s are a small client island (mousemove + framer-motion) —
 * matching the Nodus reference's hover glow. The `<Image>` itself stays a
 * plain server-rendered element with `priority`, so this doesn't touch LCP.
 */
export const HeroImage = () => {
  return (
    <Container className="border-divide relative flex items-start justify-start border-x bg-gray-100 p-2 perspective-distant md:p-4 lg:p-8 dark:bg-neutral-800">
      <Dot top left />
      <Dot top right />
      <Dot bottom left />
      <Dot bottom right />
      <div className="relative w-full">
        <div className="relative z-10 h-full w-full">
          <Image
            src="/nodus/dashboard@3x.png"
            alt="Gravitre product preview"
            className="w-full"
            priority
            fetchPriority="high"
            quality={75}
            sizes="(max-width: 1024px) 100vw, min(100vw, 1280px)"
            width={3312}
            height={1860}
            draggable={false}
          />
        </div>
        <div className="absolute inset-0 z-0 m-auto h-[90%] w-[95%] rounded-lg border border-(--pattern-fg) bg-[image:repeating-linear-gradient(315deg,_var(--pattern-fg)_0,_var(--pattern-fg)_1px,_transparent_0,_transparent_50%)] bg-[size:10px_10px] bg-fixed" />
      </div>
    </Container>
  )
}
