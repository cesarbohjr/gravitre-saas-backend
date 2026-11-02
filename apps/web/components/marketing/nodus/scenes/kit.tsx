"use client"

import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { LogoSVG } from "../logo"
import { NodusDotField } from "../dot-field"

/**
 * Nodus scene kit: the exact building blocks the Nodus home skeletons use
 * (How it works, Native Tools, Benefits), so every marketing graphic reads as
 * one system: white tiles on the dot field, the black Gravitre mark on a white
 * hub with the spinning conic rim, hairline connectors with a travelling
 * gradient pulse, "Connected" style badges, and windows with the three dots.
 */

export type NodusTone = "info" | "brand" | "warning"

const TONE_VAR: Record<NodusTone, string> = {
  info: "var(--info)",
  brand: "var(--brand)",
  warning: "var(--warning)",
}

/**
 * Hairline connector with the Nodus travelling pulse. `d` is drawn in a
 * `width`×`height` box; position the box with `className`/`style`.
 * The pulse runs along x (or y when `axis="y"`), start→end, or end→start with
 * `reverse`. Same timing as the Nodus lines: 2s run, 1s rest, forever.
 */
export function NodusBeam({
  d,
  width,
  height,
  tone = "info",
  axis = "x",
  reverse = false,
  duration = 2,
  delay = 0,
  className,
  style,
}: {
  d: string
  width: number
  height: number
  tone?: NodusTone
  axis?: "x" | "y"
  reverse?: boolean
  duration?: number
  delay?: number
  className?: string
  style?: CSSProperties
}) {
  const id = `nb-${useId().replace(/:/g, "")}`
  const from = reverse ? ["105%", "120%"] : ["-20%", "0%"]
  const to = reverse ? ["-20%", "0%"] : ["105%", "120%"]
  const along = axis === "x" ? ["x1", "x2"] : ["y1", "y2"]
  const across = axis === "x" ? { y1: 0, y2: 1 } : { x1: 0, x2: 1 }
  return (
    <svg
      aria-hidden
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      fill="none"
      className={cn("pointer-events-none absolute overflow-visible", className)}
      style={style}
    >
      <path d={d} stroke="var(--color-line)" strokeLinecap="round" strokeLinejoin="round" />
      <path d={d} stroke={`url(#${id})`} strokeLinecap="round" strokeLinejoin="round" />
      <defs>
        <motion.linearGradient
          id={id}
          gradientUnits="userSpaceOnUse"
          initial={{ ...across, [along[0]]: from[0], [along[1]]: from[1] }}
          animate={{ ...across, [along[0]]: to[0], [along[1]]: to[1] }}
          transition={{ duration, delay, repeat: Infinity, repeatType: "loop", ease: "easeInOut", repeatDelay: 1 }}
        >
          <stop stopColor="var(--color-line)" />
          <stop offset="0.33" stopColor={TONE_VAR[tone]} />
          <stop offset="0.66" stopColor={TONE_VAR[tone]} />
          <stop offset="1" stopColor="var(--color-line)" />
        </motion.linearGradient>
      </defs>
    </svg>
  )
}

/**
 * NodusBeam through absolute stage points, e.g. an elbow from a label to the
 * hub: [[150, 80], [230, 80], [230, 160], [260, 160]]. The pulse runs from the
 * first point to the last along the longer axis.
 */
export function NodusPath({
  points,
  tone = "info",
  delay = 0,
  duration = 2,
}: {
  points: [number, number][]
  tone?: NodusTone
  delay?: number
  duration?: number
}) {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  const left = Math.min(...xs)
  const top = Math.min(...ys)
  const width = Math.max(2, Math.max(...xs) - left)
  const height = Math.max(2, Math.max(...ys) - top)
  const [first, last] = [points[0], points[points.length - 1]]
  const axis = Math.abs(last[0] - first[0]) >= Math.abs(last[1] - first[1]) ? "x" : "y"
  const reverse = axis === "x" ? last[0] < first[0] : last[1] < first[1]
  const d = points.map((p, i) => `${i ? "L" : "M"}${p[0] - left + 0.5},${p[1] - top + 0.5}`).join(" ")
  return (
    <NodusBeam
      d={d}
      width={width + 1}
      height={height + 1}
      tone={tone}
      axis={axis}
      reverse={reverse}
      delay={delay}
      duration={duration}
      style={{ left, top }}
    />
  )
}

/** The Nodus hub: white tile, black Gravitre mark, spinning info/brand conic rim. */
export function NodusHub({ size = 64, className, style }: { size?: number; className?: string; style?: CSSProperties }) {
  return (
    <div
      className={cn("mk-ambient relative shrink-0 overflow-hidden rounded-md bg-gray-200 p-px shadow-xl", className)}
      style={{ width: size, height: size, ...style }}
    >
      <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [background-image:conic-gradient(at_center,transparent,var(--info)_20%,transparent_30%)] [animation-duration:2s]" />
      <div className="absolute inset-0 scale-[1.4] animate-spin rounded-full [background-image:conic-gradient(at_center,transparent,var(--color-brand)_20%,transparent_30%)] [animation-delay:1s] [animation-duration:2s]" />
      <div
        className="relative z-20 flex h-full w-full items-center justify-center rounded-[5px] bg-card text-foreground"
        style={{ padding: size * 0.22 }}
      >
        <LogoSVG style={{ width: size * 0.375, height: size * 0.375 }} />
      </div>
    </div>
  )
}

/** Nodus IconBlock: 48px white tile, hairline border, soft shadow. */
export function NodusTile({
  children,
  className,
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      className={cn(
        "relative flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-card shadow-md [&>svg]:size-6",
        className,
      )}
      style={style}
    >
      {children}
    </div>
  )
}

/** Nodus status badge ("Connected"). */
export function NodusBadge({
  children,
  tone = "info",
  className,
  style,
}: {
  children: ReactNode
  tone?: NodusTone
  className?: string
  style?: CSSProperties
}) {
  return (
    <span
      className={cn(
        "relative z-20 inline-flex items-center rounded-sm border px-2 py-0.5 text-xs whitespace-nowrap",
        tone === "info" && "border-info bg-info/10 text-info",
        tone === "brand" && "border-brand bg-brand/10 text-brand",
        tone === "warning" && "border-warning bg-warning/10 text-warning",
        className,
      )}
      style={style}
    >
      {children}
    </span>
  )
}

/** Nodus text + icon row ("Meeting Summarizer"). */
export function NodusLabel({ icon, children, className }: { icon: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cn("relative flex items-center gap-2 [&>svg]:size-4 [&>svg]:shrink-0", className)}>
      {icon}
      <span className="text-charcoal-700 text-sm font-medium whitespace-nowrap">{children}</span>
    </div>
  )
}

/** Nodus window: white card, top hairline, three dots. */
export function NodusWindow({
  title,
  children,
  className,
  style,
}: {
  title?: ReactNode
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      className={cn("shadow-aceternity relative rounded-xl bg-card p-3", className)}
      style={style}
    >
      <div className="mb-3 flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-destructive" />
        <span className="size-2.5 rounded-full bg-warning" />
        <span className="size-2.5 rounded-full bg-brand" />
        {title ? <span className="text-charcoal-700 ml-2 text-xs font-medium">{title}</span> : null}
      </div>
      {children}
    </div>
  )
}

/**
 * A row inside a Nodus window. `active` gives it the light window highlight
 * (a soft brand tint and hairline), never a thick coloured outline.
 */
export function NodusRow({
  icon,
  label,
  meta,
  active = false,
  className,
}: {
  icon?: ReactNode
  label: ReactNode
  meta?: ReactNode
  active?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-md border px-2.5 py-2",
        active ? "border-brand/25 bg-brand/[0.06]" : "border-transparent",
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-2 [&>svg]:size-4 [&>svg]:shrink-0">
        {icon}
        <span className="text-charcoal-700 truncate text-sm font-medium">{label}</span>
      </div>
      {meta}
    </div>
  )
}

/** Grey skeleton bars, as in the Nodus cards. */
export function NodusBars({ widths = [70, 45], className }: { widths?: number[]; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {widths.map((w, i) => (
        <span key={i} className={cn("h-1.5 rounded-full", i === 0 ? "bg-gray-300" : "bg-gray-200")} style={{ width: `${w}%` }} />
      ))}
    </div>
  )
}

/**
 * Fixed-size stage scaled to its container's width, so a scene keeps its exact
 * Nodus geometry (48px tiles, 64px hub) at any column width.
 */
export function NodusStage({
  width,
  height,
  children,
  className,
  dots = true,
}: {
  width: number
  height: number
  children: ReactNode
  className?: string
  dots?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === "undefined") return
    const update = () => setScale(Math.min(1, el.getBoundingClientRect().width / width))
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [width])
  return (
    <div
      ref={ref}
      className={cn("relative isolate mx-auto w-full overflow-hidden", className)}
      style={{ aspectRatio: `${width} / ${height}`, maxWidth: width }}
    >
      {dots ? <NodusDotField className="-z-10" /> : null}
      <div
        className="absolute top-0 left-1/2 origin-top"
        style={{ width, height, transform: `translateX(-50%) scale(${scale})` }}
      >
        {children}
      </div>
    </div>
  )
}
