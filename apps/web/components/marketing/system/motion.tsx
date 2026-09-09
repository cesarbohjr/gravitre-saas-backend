"use client"

/**
 * Marketing System 4.0 — semantic motion primitives.
 * Primary runtime: framer-motion. Respects prefers-reduced-motion.
 * Do not default to fade-up for every section — pick FLOW / TRACE / PULSE / RESOLVE / FOCUS.
 */

import { type ReactNode } from "react"
import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion"
import { cn } from "@/lib/utils"

type MotionKind = "reveal" | "flow" | "trace" | "pulse" | "resolve" | "focus"

const ENTER: Record<
  MotionKind,
  { hidden: Record<string, number>; show: Record<string, number | number[]> }
> = {
  reveal: {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0 },
  },
  flow: {
    hidden: { opacity: 0, x: -16 },
    show: { opacity: 1, x: 0 },
  },
  trace: {
    hidden: { opacity: 0, scale: 0.98 },
    show: { opacity: 1, scale: 1 },
  },
  pulse: {
    hidden: { opacity: 0.55, scale: 0.96 },
    show: { opacity: 1, scale: 1 },
  },
  resolve: {
    hidden: { opacity: 0, y: 8, filter: "blur(4px)" },
    show: { opacity: 1, y: 0, filter: "blur(0px)" },
  },
  focus: {
    hidden: { opacity: 0.4 },
    show: { opacity: 1 },
  },
}

const DURATION: Record<MotionKind, number> = {
  reveal: 0.4,
  flow: 0.55,
  trace: 0.65,
  pulse: 0.45,
  resolve: 0.5,
  focus: 0.25,
}

export function GravitreReveal({
  children,
  className,
  kind = "reveal",
  delay = 0,
  once = true,
  ...rest
}: {
  children: ReactNode
  className?: string
  kind?: MotionKind
  delay?: number
  once?: boolean
} & Omit<HTMLMotionProps<"div">, "children">) {
  const reduce = useReducedMotion()
  const preset = ENTER[kind]

  if (reduce) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once, amount: 0.25 }}
      variants={{
        hidden: preset.hidden,
        show: {
          ...preset.show,
          transition: {
            duration: DURATION[kind],
            delay,
            ease: [0.16, 1, 0.3, 1],
          },
        },
      }}
      {...rest}
    >
      {children}
    </motion.div>
  )
}

export function GravitreFlow(props: Omit<Parameters<typeof GravitreReveal>[0], "kind">) {
  return <GravitreReveal kind="flow" {...props} />
}

export function GravitreTrace(props: Omit<Parameters<typeof GravitreReveal>[0], "kind">) {
  return <GravitreReveal kind="trace" {...props} />
}

export function GravitrePulse(props: Omit<Parameters<typeof GravitreReveal>[0], "kind">) {
  return <GravitreReveal kind="pulse" {...props} />
}

export function GravitreResolve(props: Omit<Parameters<typeof GravitreReveal>[0], "kind">) {
  return <GravitreReveal kind="resolve" {...props} />
}

export function GravitreAmbientMotion({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  const reduce = useReducedMotion()
  if (reduce) {
    return <div className={cn("opacity-70", className)}>{children}</div>
  }
  return (
    <motion.div
      className={className}
      animate={{ opacity: [0.55, 0.85, 0.55] }}
      transition={{ duration: 12, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
    >
      {children}
    </motion.div>
  )
}
