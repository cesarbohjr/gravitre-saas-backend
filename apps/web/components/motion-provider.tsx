"use client"

import { MotionConfig } from "framer-motion"
import type { ReactNode } from "react"

/**
 * App-wide motion configuration.
 *
 * `reducedMotion="user"` makes every framer-motion component automatically
 * respect the OS-level `prefers-reduced-motion` setting: transform-based
 * animations (x/y/scale/rotate) and layout animations are disabled while
 * opacity transitions are preserved. This guarantees a baseline of motion
 * accessibility across all 100+ animated surfaces without per-component code,
 * complementing the finer-grained `useMotionPrefs()` hook in lib/animations.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>
}
