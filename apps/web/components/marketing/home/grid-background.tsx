"use client"

import { motion } from "framer-motion"
import { NeuralLines } from "./neural-lines"

/** Ambient field for marketing sections — graphite + restrained intelligence/emerald. */
export function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-[color:var(--g-intelligence)]/10 via-background to-[color:var(--g-emerald)]/8" />

      <motion.div
        className="absolute left-1/4 top-0 h-[600px] w-[600px] rounded-full bg-gradient-to-br from-[color:var(--g-emerald)]/20 to-transparent blur-3xl"
        animate={{
          x: [0, 100, 0],
          y: [0, 50, 0],
          scale: [1, 1.1, 1],
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 right-1/4 h-[500px] w-[500px] rounded-full bg-gradient-to-br from-[color:var(--g-signal)]/15 to-transparent blur-3xl"
        animate={{
          x: [0, -80, 0],
          y: [0, -60, 0],
          scale: [1, 1.2, 1],
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
      <motion.div
        className="absolute right-0 top-1/3 h-[400px] w-[400px] rounded-full bg-gradient-to-br from-[color:var(--g-intelligence)]/18 to-transparent blur-3xl"
        animate={{
          x: [0, -50, 0],
          y: [0, 100, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 4 }}
      />

      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `
            linear-gradient(var(--foreground) 1px, transparent 1px),
            linear-gradient(90deg, var(--foreground) 1px, transparent 1px)
          `,
          backgroundSize: "64px 64px",
        }}
      />

      <NeuralLines />
    </div>
  )
}
