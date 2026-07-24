"use client"

import { motion } from "framer-motion"

export function AnimatedStat({
  value,
  label,
  suffix = "",
}: {
  value: string
  label: string
  suffix?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="relative group"
    >
      <div className="absolute -inset-4 rounded-2xl bg-gradient-to-b from-emerald-50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="relative text-center">
        <motion.div
          className="text-5xl sm:text-6xl font-bold text-zinc-900"
          whileInView={{ scale: [0.5, 1] }}
          transition={{ type: "spring", stiffness: 200 }}
        >
          {value}
          {suffix}
        </motion.div>
        <div className="mt-2 text-sm text-zinc-500">{label}</div>
      </div>
    </motion.div>
  )
}
