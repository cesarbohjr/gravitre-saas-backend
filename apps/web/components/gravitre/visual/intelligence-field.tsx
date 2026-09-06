"use client"

/**
 * Gravitre Intelligence Field — Design Pass 2 Agenforce-caliber environment.
 * Layers: Atmosphere · Structure · Signal · Local light · Depth (pointer).
 * Marketing homepage. No WebGL. Caps: ≤20 paths, ≤1 concurrent signal.
 */

import { motion, useMotionTemplate, useMotionValue, useSpring } from "framer-motion"
import { useEffect, useMemo, useState } from "react"
import { useMotionPrefs } from "@/lib/animations"
import { cn } from "@/lib/utils"
import { GravitreSignal, type GravitreSignalTone } from "./gravitre-signal"

const VIEW_W = 800
const VIEW_H = 560

const FULL_NODES = [
  { id: "c1", x: 90, y: 180 },
  { id: "c2", x: 120, y: 320 },
  { id: "c3", x: 160, y: 440 },
  { id: "hub", x: 380, y: 260 },
  { id: "agent", x: 560, y: 200 },
  { id: "tool", x: 620, y: 340 },
  { id: "approve", x: 700, y: 240 },
  { id: "out", x: 760, y: 360 },
  { id: "mem", x: 340, y: 120 },
  { id: "gibe", x: 420, y: 400 },
] as const

const MOBILE_NODE_IDS = new Set(["c1", "c2", "hub", "agent", "approve", "out"])

const FULL_PATHS: { id: string; d: string; signal?: boolean }[] = [
  { id: "p1", d: "M90 180C180 200 280 230 380 260" },
  { id: "p2", d: "M120 320C220 300 300 270 380 260" },
  { id: "p3", d: "M160 440C260 400 320 320 380 260" },
  { id: "p4", d: "M380 260C460 230 510 210 560 200", signal: true },
  { id: "p5", d: "M560 200C600 250 610 300 620 340" },
  { id: "p6", d: "M560 200C620 210 660 225 700 240" },
  { id: "p7", d: "M700 240C730 290 745 330 760 360" },
  { id: "p8", d: "M380 260C360 200 350 150 340 120" },
  { id: "p9", d: "M380 260C395 320 405 360 420 400" },
  { id: "p10", d: "M620 340C680 350 720 355 760 360" },
]

const SIGNAL_STORY: { tone: GravitreSignalTone; delayMs: number }[] = [
  { tone: "signal", delayMs: 600 },
  { tone: "intelligence", delayMs: 0 },
  { tone: "operational", delayMs: 0 },
]

/** Section atmospheric narrative — violet → cyan → violet+signal → amber → emerald → balanced */
export type FieldAtmosphere =
  | "intelligence"
  | "systems"
  | "agents"
  | "approval"
  | "outcome"
  | "balanced"

type IntelligenceFieldProps = {
  className?: string
  variant?: "hero" | "section"
  atmosphere?: FieldAtmosphere
}

function atmosphereWash(atmosphere: FieldAtmosphere, isDark: boolean) {
  switch (atmosphere) {
    case "systems":
      return {
        primary: isDark
          ? ("radial-gradient(circle at center, var(--g-signal) 0%, transparent 70%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-signal) 22%, transparent) 0%, transparent 72%)" as const),
        secondary: isDark
          ? ("radial-gradient(circle at center, var(--g-emerald) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-emerald) 16%, transparent) 0%, transparent 72%)" as const),
        primaryOpacity: isDark ? ([0.03, 0.055, 0.03] as const) : ([0.03, 0.05, 0.03] as const),
        secondaryOpacity: isDark ? ([0.02, 0.04, 0.02] as const) : ([0.025, 0.04, 0.025] as const),
      }
    case "approval":
      return {
        primary: isDark
          ? ("radial-gradient(circle at center, var(--g-warning) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-warning) 18%, transparent) 0%, transparent 72%)" as const),
        secondary: isDark
          ? ("radial-gradient(circle at center, var(--g-intelligence) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-intelligence) 14%, transparent) 0%, transparent 72%)" as const),
        primaryOpacity: isDark ? ([0.025, 0.045, 0.025] as const) : ([0.025, 0.045, 0.025] as const),
        secondaryOpacity: isDark ? ([0.03, 0.05, 0.03] as const) : ([0.03, 0.05, 0.03] as const),
      }
    case "outcome":
      return {
        primary: isDark
          ? ("radial-gradient(circle at center, var(--g-emerald) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-emerald) 24%, transparent) 0%, transparent 72%)" as const),
        secondary: isDark
          ? ("radial-gradient(circle at center, var(--g-intelligence) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-intelligence) 14%, transparent) 0%, transparent 72%)" as const),
        primaryOpacity: isDark ? ([0.04, 0.075, 0.04] as const) : ([0.035, 0.06, 0.035] as const),
        secondaryOpacity: isDark ? ([0.025, 0.045, 0.025] as const) : ([0.025, 0.04, 0.025] as const),
      }
    case "balanced":
      return {
        primary: isDark
          ? ("radial-gradient(circle at center, var(--g-intelligence) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-intelligence) 22%, transparent) 0%, transparent 72%)" as const),
        secondary: isDark
          ? ("radial-gradient(circle at center, var(--g-emerald) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-emerald) 22%, transparent) 0%, transparent 72%)" as const),
        primaryOpacity: isDark ? ([0.04, 0.07, 0.04] as const) : ([0.035, 0.06, 0.035] as const),
        secondaryOpacity: isDark ? ([0.035, 0.065, 0.035] as const) : ([0.03, 0.055, 0.03] as const),
      }
    case "agents":
    case "intelligence":
    default:
      return {
        primary: isDark
          ? ("radial-gradient(circle at center, var(--g-intelligence) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-intelligence) 16%, transparent) 0%, transparent 72%)" as const),
        secondary: isDark
          ? ("radial-gradient(circle at center, var(--g-emerald) 0%, transparent 68%)" as const)
          : ("radial-gradient(ellipse 70% 55% at 50% 50%, color-mix(in oklch, var(--g-emerald) 14%, transparent) 0%, transparent 72%)" as const),
        primaryOpacity: isDark
          ? atmosphere === "agents"
            ? ([0.05, 0.09, 0.05] as const)
            : ([0.055, 0.1, 0.055] as const)
          : ([0.03, 0.055, 0.03] as const),
        secondaryOpacity: isDark ? ([0.03, 0.055, 0.03] as const) : ([0.025, 0.045, 0.025] as const),
      }
  }
}

export function IntelligenceField({
  className,
  variant = "hero",
  atmosphere = "intelligence",
}: IntelligenceFieldProps) {
  const { reduced } = useMotionPrefs()
  const [mobile, setMobile] = useState(false)
  const [storyIndex, setStoryIndex] = useState(0)

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px), (pointer: coarse)")
    const apply = () => setMobile(mq.matches)
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [])

  useEffect(() => {
    if (reduced || variant !== "hero") return
    const id = window.setInterval(() => {
      setStoryIndex((i) => (i + 1) % SIGNAL_STORY.length)
    }, 11000)
    return () => window.clearInterval(id)
  }, [reduced, variant])

  const nodes = useMemo(
    () =>
      mobile ? FULL_NODES.filter((n) => MOBILE_NODE_IDS.has(n.id)) : [...FULL_NODES],
    [mobile],
  )

  const paths = useMemo(() => {
    if (!mobile) return FULL_PATHS
    const keep = new Set(["p1", "p2", "p4", "p6", "p7"])
    return FULL_PATHS.filter((p) => keep.has(p.id))
  }, [mobile])

  const signalPath = paths.find((p) => p.signal)?.d ?? paths[0]?.d ?? FULL_PATHS[3].d
  const story = SIGNAL_STORY[storyIndex] ?? SIGNAL_STORY[0]

  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const springX = useSpring(mx, { stiffness: 60, damping: 20 })
  const springY = useSpring(my, { stiffness: 60, damping: 20 })
  const midTransform = useMotionTemplate`translate(${springX}px, ${springY}px)`

  useEffect(() => {
    if (reduced || mobile || variant !== "hero") return
    const onMove = (e: PointerEvent) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2
      const ny = (e.clientY / window.innerHeight - 0.5) * 2
      mx.set(nx * 5)
      my.set(ny * 4)
    }
    window.addEventListener("pointermove", onMove, { passive: true })
    return () => window.removeEventListener("pointermove", onMove)
  }, [reduced, mobile, variant, mx, my])

  const [isDark, setIsDark] = useState(false)
  useEffect(() => {
    const root = document.documentElement
    const apply = () => setIsDark(root.classList.contains("dark"))
    apply()
    const obs = new MutationObserver(apply)
    obs.observe(root, { attributes: true, attributeFilter: ["class"] })
    return () => obs.disconnect()
  }, [])

  const isHero = variant === "hero"
  const atmosphereOpacity = isHero ? 1 : 0.55
  const graphOpacity = isHero ? 0.85 : atmosphere === "agents" ? 0.5 : 0.35
  const wash = atmosphereWash(atmosphere, isDark)
  // Light canvas: restrained topology; dark B2: stronger path weight for boldness.
  const pathStrokeOpacity = isDark ? 0.38 : 0.22
  const gridOpacity = isDark ? 0.055 : 0.028
  const useBlurAtmosphere = isDark
  const showSignal = isHero || atmosphere === "agents" || atmosphere === "outcome"

  return (
    <div
      aria-hidden
      data-field-atmosphere={atmosphere}
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      {/* Layer 1 — Atmosphere */}
      <div className="absolute inset-0" style={{ opacity: atmosphereOpacity }}>
        {reduced ? (
          <>
            <div
              className="absolute -left-1/4 top-0 h-[75%] w-[75%] rounded-full"
              style={{
                opacity: wash.primaryOpacity[1],
                background: wash.primary,
                filter: useBlurAtmosphere ? "blur(var(--g-blur-atmosphere))" : undefined,
              }}
            />
            <div
              className="absolute -right-1/5 bottom-0 h-[70%] w-[70%] rounded-full"
              style={{
                opacity: wash.secondaryOpacity[1],
                background: wash.secondary,
                filter: useBlurAtmosphere ? "blur(var(--g-blur-atmosphere))" : undefined,
              }}
            />
          </>
        ) : (
          <>
            <motion.div
              className="absolute -left-1/4 top-0 h-[75%] w-[75%] rounded-full"
              style={{
                background: wash.primary,
                filter: useBlurAtmosphere ? "blur(var(--g-blur-atmosphere))" : undefined,
              }}
              animate={{ opacity: [...wash.primaryOpacity] }}
              transition={{
                duration: 16,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
            <motion.div
              className="absolute -right-1/5 bottom-[-10%] h-[70%] w-[70%] rounded-full"
              style={{
                background: wash.secondary,
                filter: useBlurAtmosphere ? "blur(var(--g-blur-atmosphere))" : undefined,
              }}
              animate={{ opacity: [...wash.secondaryOpacity] }}
              transition={{
                duration: 18,
                repeat: Infinity,
                ease: "easeInOut",
                delay: 2.5,
              }}
            />
          </>
        )}
        <div
          className="absolute inset-0"
          style={{
            opacity: gridOpacity,
            backgroundImage: `
              linear-gradient(var(--foreground) 1px, transparent 1px),
              linear-gradient(90deg, var(--foreground) 1px, transparent 1px)
            `,
            backgroundSize: "72px 72px",
          }}
        />
        {/* Fine topology noise — craft texture, not busy */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 1px 1px, color-mix(in oklch, var(--foreground) 40%, transparent) 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />
      </div>

      {/* Layer 4 — Local spotlight behind product focus (hero) */}
      {isHero ? (
        <div
          className="absolute left-1/2 top-[42%] h-[55%] w-[70%] -translate-x-1/2 rounded-full"
          style={{
            background:
              "radial-gradient(ellipse at center, color-mix(in oklch, var(--g-intelligence) 16%, transparent) 0%, transparent 70%)",
            opacity: isDark ? 0.85 : 0.55,
          }}
        />
      ) : null}

      {/* Layer 2 + 3 — Org graph + live signal */}
      <motion.div
        className="absolute inset-0"
        style={{
          opacity: graphOpacity,
          transform: reduced || mobile || !isHero ? undefined : midTransform,
        }}
      >
        <svg
          className="absolute inset-0 h-full w-full"
          width="100%"
          height="100%"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          fill="none"
          preserveAspectRatio="xMidYMid slice"
        >
          {paths.map((p) => (
            <path
              key={p.id}
              d={p.d}
              stroke="var(--g-border-default)"
              strokeOpacity={pathStrokeOpacity}
              strokeWidth={0.9}
            />
          ))}
          {nodes.map((n) => {
            const isHub = n.id === "hub" || n.id === "gibe"
            const isOut = n.id === "out" || n.id === "approve"
            return (
              <circle
                key={n.id}
                cx={n.x}
                cy={n.y}
                r={isHub ? 3.2 : 2.2}
                fill={
                  isHub
                    ? "var(--g-intelligence)"
                    : isOut
                      ? "var(--g-emerald)"
                      : "var(--g-signal)"
                }
                fillOpacity={isDark ? (isHub ? 0.5 : 0.3) : isHub ? 0.55 : 0.38}
              />
            )
          })}
          {showSignal ? (
            <GravitreSignal
              key={`${story.tone}-${storyIndex}-${atmosphere}`}
              path={signalPath}
              tone={
                atmosphere === "approval"
                  ? "pending"
                  : atmosphere === "outcome"
                    ? "operational"
                    : atmosphere === "systems"
                      ? "signal"
                      : story.tone
              }
              reduced={reduced}
              cycleMs={10000}
              delayMs={story.delayMs}
            />
          ) : null}
        </svg>
      </motion.div>
    </div>
  )
}
