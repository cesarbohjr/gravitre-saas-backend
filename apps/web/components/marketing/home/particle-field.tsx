"use client"

import { motion } from "framer-motion"

function seededUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453
  return value - Math.floor(value)
}

export function ParticleField() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {Array.from({ length: 50 }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-primary/100/30 rounded-full"
          initial={{
            x: `${seededUnit(i + 1) * 100}%`,
            y: `${seededUnit(i + 101) * 100}%`,
            scale: seededUnit(i + 201) * 0.5 + 0.5,
          }}
          animate={{
            y: [`${seededUnit(i + 301) * 100}%`, `${seededUnit(i + 401) * 100}%`],
            x: [`${seededUnit(i + 501) * 100}%`, `${seededUnit(i + 601) * 100}%`],
            opacity: [0.2, 0.6, 0.2],
          }}
          transition={{
            duration: seededUnit(i + 701) * 20 + 10,
            repeat: Infinity,
            ease: "linear",
          }}
        />
      ))}
    </div>
  )
}
