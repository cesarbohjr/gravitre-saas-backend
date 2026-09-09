"use client"

import { motion, AnimatePresence } from "framer-motion"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { NETWORK_VB, CORE_STATE_LABEL, type CoreState } from "./types"

export function GravitreIntelligenceCore({
  state = "idle",
  reduced = false,
}: {
  state?: CoreState
  reduced?: boolean
}) {
  const label = CORE_STATE_LABEL[state]
  const pulsing = state !== "idle" && state !== "verified" && state !== "learned" && !reduced
  const resolved = state === "verified" || state === "learned"

  return (
    <g transform={`translate(${NETWORK_VB.cx} ${NETWORK_VB.cy})`}>
      {/* Faint radial intelligence field */}
      <circle
        r={78}
        fill="url(#gv-dept-core-field)"
        opacity={0.9}
      />
      {/* Concentric rings */}
      {[52, 64, 76].map((r) => (
        <circle
          key={r}
          r={r}
          fill="none"
          stroke="color-mix(in oklch, var(--g-intelligence) 18%, #eaedf1)"
          strokeWidth={0.75}
        />
      ))}
      {!reduced ? (
        <motion.circle
          r={58}
          fill="none"
          stroke="color-mix(in oklch, var(--color-brand, #16a374) 35%, transparent)"
          strokeWidth={1}
          initial={false}
          animate={
            pulsing
              ? { scale: [1, 1.06, 1], opacity: [0.35, 0.7, 0.35] }
              : { scale: 1, opacity: 0.25 }
          }
          transition={{ duration: 2.4, repeat: pulsing ? Infinity : 0, ease: "easeInOut" }}
        />
      ) : null}

      {/* Hub tile — Nodus language */}
      <motion.g
        initial={false}
        animate={{ scale: pulsing ? 1.03 : resolved ? 1.02 : 1 }}
        transition={{ duration: 0.4 }}
      >
        <rect
          x={-28}
          y={-28}
          width={56}
          height={56}
          rx={10}
          fill="#fff"
          stroke={
            resolved
              ? "var(--color-brand, #16a374)"
              : pulsing
                ? "color-mix(in oklch, var(--color-blue-500) 50%, #eaedf1)"
                : "var(--color-line, #eaedf1)"
          }
          strokeWidth={1.5}
        />
        <foreignObject x={-14} y={-18} width={28} height={28}>
          <div className="flex h-7 w-7 items-center justify-center text-[color:var(--color-brand,#16a374)]">
            <LogoSVG className="size-5" />
          </div>
        </foreignObject>
        <text
          y={22}
          textAnchor="middle"
          style={{ fontSize: 8, fontWeight: 700, letterSpacing: "0.06em" }}
          className="fill-[color:var(--g-text-muted)] uppercase"
        >
          Core
        </text>
      </motion.g>

      <AnimatePresence mode="wait">
        {label ? (
          <motion.g
            key={state}
            initial={reduced ? false : { opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <rect
              x={-58}
              y={36}
              width={116}
              height={22}
              rx={6}
              fill="#fff"
              stroke="var(--color-line, #eaedf1)"
              strokeWidth={1}
            />
            <text
              y={50}
              textAnchor="middle"
              style={{ fontSize: 9, fontWeight: 600 }}
              className="fill-[color:var(--color-brand,#16a374)]"
            >
              {label}
            </text>
          </motion.g>
        ) : null}
      </AnimatePresence>
    </g>
  )
}
