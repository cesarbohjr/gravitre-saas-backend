import React from "react"
import Image from "next/image"
import { motion } from "framer-motion"
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
  /** When set, the screenshot fades/rises in each time this key changes. */
  animateKey?: string
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
  animateKey,
}: HeroImageProps = {}) => {
  const image = (
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
  )
  return (
    <Container className="border-divide relative flex items-start justify-start md:border-x bg-white p-4 perspective-distant md:p-8 lg:p-12">
      <Dot top left />
      <Dot top right />
      <Dot bottom left />
      <Dot bottom right />
      <div className="relative isolate w-full">
        <AppWindow title={title} chips={chips} className="z-10 h-full w-full">
          {animateKey ? (
            <motion.div
              key={animateKey}
              initial={{ opacity: 0, y: 14, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
            >
              {image}
            </motion.div>
          ) : (
            image
          )}
        </AppWindow>
      </div>
    </Container>
  )
}
