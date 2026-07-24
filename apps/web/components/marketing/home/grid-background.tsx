"use client"

import { motion } from "framer-motion"
import { NeuralLines } from "./neural-lines"

export function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-emerald-50/80 via-white to-blue-50/50" />

      <motion.div
        className="absolute top-0 left-1/4 w-[600px] h-[600px] rounded-full bg-gradient-to-br from-emerald-200/40 to-transparent blur-3xl"
        animate={{
          x: [0, 100, 0],
          y: [0, 50, 0],
          scale: [1, 1.1, 1],
        }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 right-1/4 w-[500px] h-[500px] rounded-full bg-gradient-to-br from-blue-200/30 to-transparent blur-3xl"
        animate={{
          x: [0, -80, 0],
          y: [0, -60, 0],
          scale: [1, 1.2, 1],
        }}
        transition={{ duration: 15, repeat: Infinity, ease: "easeInOut", delay: 2 }}
      />
      <motion.div
        className="absolute top-1/3 right-0 w-[400px] h-[400px] rounded-full bg-gradient-to-br from-purple-100/30 to-transparent blur-3xl"
        animate={{
          x: [0, -50, 0],
          y: [0, 100, 0],
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 4 }}
      />

      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,0,0,0.1) 1px, transparent 1px)
          `,
          backgroundSize: "64px 64px",
        }}
      />

      <NeuralLines />

      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-500/40 to-transparent"
        animate={{ y: [0, 1000] }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
      />
      <motion.div
        className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-blue-500/20 to-transparent"
        animate={{ y: [0, 1000] }}
        transition={{ duration: 12, repeat: Infinity, ease: "linear", delay: 4 }}
      />

      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full border border-emerald-500/10"
        animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut" }}
      />
      <motion.div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full border border-emerald-500/10"
        animate={{ scale: [1, 2.5], opacity: [0.4, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeOut", delay: 2 }}
      />

      {[
        { left: "10%", top: "20%", dur: 5 },
        { left: "25%", top: "15%", dur: 6 },
        { left: "40%", top: "30%", dur: 4 },
        { left: "60%", top: "10%", dur: 7 },
        { left: "75%", top: "25%", dur: 5 },
        { left: "85%", top: "35%", dur: 6 },
        { left: "15%", top: "50%", dur: 4 },
        { left: "30%", top: "60%", dur: 5 },
        { left: "50%", top: "45%", dur: 6 },
        { left: "70%", top: "55%", dur: 4 },
        { left: "90%", top: "50%", dur: 7 },
        { left: "5%", top: "70%", dur: 5 },
        { left: "20%", top: "80%", dur: 6 },
        { left: "45%", top: "75%", dur: 4 },
        { left: "65%", top: "85%", dur: 5 },
        { left: "80%", top: "70%", dur: 6 },
      ].map((p, i) => (
        <motion.div
          key={i}
          className="absolute w-1.5 h-1.5 bg-emerald-400/50 rounded-full"
          style={{ left: p.left, top: p.top }}
          animate={{
            y: [0, -25, 0],
            opacity: [0.3, 0.7, 0.3],
            scale: [1, 1.3, 1],
          }}
          transition={{
            duration: p.dur,
            repeat: Infinity,
            delay: i * 0.3,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  )
}
