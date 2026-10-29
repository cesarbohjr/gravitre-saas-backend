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
    <Container className="border-divide relative flex items-start justify-start md:border-x bg-[#efefea] p-2 perspective-distant md:p-6 lg:p-12">
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
        {/* Soft colour wash — the same mint / sand blobs the app's illustrations sit on. */}
        <div
          aria-hidden
          className="absolute -inset-2 z-0 md:-inset-6 lg:-inset-12 bg-[radial-gradient(55%_65%_at_18%_30%,#ddf3e8_0,transparent_70%),radial-gradient(45%_55%_at_88%_78%,#f2e4d0_0,transparent_70%),radial-gradient(35%_45%_at_70%_10%,#e3e3f3_0,transparent_70%)]"
        />
      </div>
    </Container>
  )
}
