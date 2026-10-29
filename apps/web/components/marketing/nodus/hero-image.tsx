import React from "react"
import Image from "next/image"
import { Container } from "./container"
import { Dot } from "./common/dots"
import { AppWindow, type AppWindowChip } from "./app-window"

/**
 * Hero product screenshot in a macOS window outline — server-rendered for crisp marketing display.
 * Defaults to the full-resolution dashboard capture in public/nodus/; other
 * pages pass their own capture (scripts/capture-product-shots.mjs).
 *
 * The corner `Dot`s are a small client island (mousemove + framer-motion) —
 * matching the Nodus reference's hover glow. The `<Image>` itself stays a
 * plain server-rendered element with `priority`, so this doesn't touch LCP.
 */
type HeroImageProps = {
  src?: string
  alt?: string
  width?: number
  height?: number
  /** Title pill in the window bar. */
  title?: string
  chips?: AppWindowChip[]
}

export const HeroImage = ({
  src = "/nodus/dashboard@3x.png",
  alt = "Gravitre product preview",
  width = 3312,
  height = 1863,
  title = "Dashboard",
  chips = [
    { label: "Live · updated just now", at: "top-right" },
    { label: "Human approval on every write", at: "bottom-left", tone: "amber" },
  ],
}: HeroImageProps = {}) => {
  return (
    <Container className="border-divide relative flex items-start justify-start md:border-x bg-white p-4 perspective-distant md:p-8 lg:p-12">
      <Dot top left />
      <Dot top right />
      <Dot bottom left />
      <Dot bottom right />
      <div className="relative isolate w-full">
        <AppWindow title={title} chips={chips} className="z-10 h-full w-full">
          <Image
            src={src}
            alt={alt}
            className="block w-full"
            priority
            fetchPriority="high"
            quality={75}
            sizes="(max-width: 1024px) 100vw, min(100vw, 1280px)"
            width={width}
            height={height}
            draggable={false}
          />
        </AppWindow>
      </div>
    </Container>
  )
}
