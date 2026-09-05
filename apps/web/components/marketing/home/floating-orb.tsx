"use client"

import { motion } from "framer-motion"
import { useMotionPrefs } from "@/lib/animations"

export function FloatingOrb({ className, delay = 0 }: { className: string; delay?: number }) {
  const { reduced } = useMotionPrefs()

  if (reduced) {
    return <div aria-hidden className={`absolute rounded-full blur-3xl opacity-25 ${className}`} />
  }

  return (
    <motion.div
      aria-hidden
      className={`absolute rounded-full blur-3xl ${className}`}
      animate={{
        y: [0, -30, 0],
        scale: [1, 1.1, 1],
        opacity: [0.2, 0.3, 0.2],
      }}
      transition={{
        duration: 8,
        delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  )
}
