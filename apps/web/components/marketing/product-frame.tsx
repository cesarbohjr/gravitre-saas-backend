"use client"

/**
 * Art-directed Gravitre product screenshot treatments (Design Pass 2 Agenforce-caliber).
 * Uses real captures from /public/product — no fabricated dashboards.
 */

import Image from "next/image"
import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"

export type ProductFrameTreatment =
  | "full"
  | "perspective"
  | "detail"
  | "fade-system"
  | "stacked"

export type ProductFrameProps = {
  src: string
  alt: string
  caption?: string
  chromeLabel?: string
  treatment?: ProductFrameTreatment
  priority?: boolean
  glowTone?: "intelligence" | "operational" | "none"
  className?: string
  /** Secondary shot for stacked treatment */
  secondarySrc?: string
  secondaryAlt?: string
}

export function ProductFrame({
  src,
  alt,
  caption,
  chromeLabel = "gravitre.app",
  treatment = "full",
  priority = false,
  glowTone = "intelligence",
  className,
  secondarySrc,
  secondaryAlt,
}: ProductFrameProps) {
  const { reduced } = useMotionPrefs()
  const isPerspective = treatment === "perspective" && !reduced
  const isFade = treatment === "fade-system"
  const isDetail = treatment === "detail"
  const isStacked = treatment === "stacked" && Boolean(secondarySrc)

  const glowClass =
    glowTone === "operational"
      ? "bg-[color:var(--g-emerald)]/10"
      : glowTone === "intelligence"
        ? "bg-[color:var(--g-intelligence)]/8"
        : ""

  const frame = (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] shadow-[var(--g-shadow-product)]",
        isDetail && "rounded-xl",
      )}
      style={{
        boxShadow: "var(--g-highlight-top), var(--g-shadow-product)",
        ...(isFade
          ? {
              maskImage:
                "linear-gradient(to bottom, black 0%, black 68%, transparent 100%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, black 0%, black 68%, transparent 100%)",
            }
          : {}),
      }}
    >
      <div className="flex items-center gap-2 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
          <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/22" />
          <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--g-emerald)]/55" />
        </div>
        <div className="flex flex-1 justify-center">
          <span className="rounded-md bg-muted/60 px-2.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            {chromeLabel}
          </span>
        </div>
      </div>
      <Image
        src={src}
        alt={alt}
        width={2880}
        height={1800}
        priority={priority}
        sizes="(min-width: 1024px) 960px, 100vw"
        className={cn("h-auto w-full", isDetail && "scale-[1.08] origin-top")}
      />
    </div>
  )

  return (
    <figure className={cn("relative flex flex-col gap-3", className)}>
      {glowTone !== "none" ? (
        <div
          aria-hidden
          className={cn("absolute -inset-6 rounded-[2rem] blur-3xl opacity-55", glowClass)}
        />
      ) : null}

      <motion.div
        initial={reduced ? false : { opacity: 0, y: 28, rotateX: isPerspective ? 8 : 0 }}
        whileInView={{ opacity: 1, y: 0, rotateX: isPerspective ? 6 : 0 }}
        viewport={{ once: true, margin: "-10%" }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={
          isPerspective
            ? {
                transformPerspective: 1400,
                transformStyle: "preserve-3d",
              }
            : undefined
        }
        className={cn(
          "relative",
          isPerspective &&
            "md:[transform:perspective(1400px)_rotateX(6deg)_rotateY(-4deg)] md:origin-top",
        )}
      >
        {isStacked ? (
          <div className="relative">
            <div className="absolute inset-x-6 -top-4 z-0 scale-[0.94] opacity-45 blur-[0.5px]">
              <div className="overflow-hidden rounded-2xl border border-[color:var(--g-border-subtle)]">
                <Image
                  src={secondarySrc!}
                  alt={secondaryAlt ?? ""}
                  width={2880}
                  height={1800}
                  sizes="(min-width: 1024px) 880px, 100vw"
                  className="h-auto w-full"
                />
              </div>
            </div>
            <div className="relative z-10">{frame}</div>
          </div>
        ) : (
          frame
        )}
      </motion.div>

      {caption ? (
        <figcaption className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  )
}
