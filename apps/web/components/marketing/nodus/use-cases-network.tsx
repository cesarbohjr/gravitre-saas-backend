"use client"

import { motion, useReducedMotion } from "framer-motion"
import { NodusDotField } from "./dot-field"

/**
 * Home Use Cases hub: six department cards wired to the Gravitre mark.
 * Cards pop in one after another when the section scrolls into view, each
 * connector draws in behind its card, then a light beam runs along it to the
 * hub on a loop, the same way the Nodus skeletons animate their wiring.
 */
type Dept = {
  label: string
  color: string
  x: number
  y: number
  /** Where the connector leaves the card and where it meets the hub. */
  from: [number, number]
  to: [number, number]
}

const HUB = { x: 480, y: 150 }

const DEPTS: Dept[] = [
  { label: "Engineering", color: "#5B6E7A", x: 60, y: 55, from: [180, 82], to: [448, 140] },
  { label: "Support", color: "#E2A33A", x: 780, y: 55, from: [780, 82], to: [512, 140] },
  { label: "Sales", color: "#C98F5B", x: 40, y: 145, from: [160, 172], to: [448, 155] },
  { label: "Finance", color: "#7E9A7B", x: 800, y: 145, from: [800, 172], to: [512, 155] },
  { label: "Marketing", color: "#B5654A", x: 60, y: 225, from: [180, 252], to: [448, 168] },
  { label: "Operations", color: "#5B6E7A", x: 780, y: 225, from: [780, 252], to: [512, 168] },
]

const POP = 0.18
const START = 0.35

export function UseCasesNetwork({ className }: { className?: string }) {
  const reduce = useReducedMotion()
  const seen = { once: true, amount: 0.4 } as const

  return (
    <figure className={`relative isolate ${className ?? ""}`}>
      <NodusDotField className="-z-10" />
      <svg
        viewBox="0 0 960 300"
        className="block h-auto w-full"
        role="img"
        aria-label="Engineering, Sales, Marketing, Support, Finance and Operations wired to one Gravitre hub"
      >
        <defs>
          <filter id="uc-card-shadow" x="-10%" y="-20%" width="120%" height="150%">
            <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.06" />
          </filter>
        </defs>

        {DEPTS.map((d, i) => {
          const delay = START + i * POP
          const path = `M${d.from[0]},${d.from[1]} L${d.to[0]},${d.to[1]}`
          const length = Math.hypot(d.to[0] - d.from[0], d.to[1] - d.from[1])
          const beam = length * 0.22
          return (
            <g key={`wire-${d.label}`}>
              <motion.path
                d={path}
                stroke="#E4E4E7"
                strokeWidth={1.5}
                fill="none"
                initial={reduce ? false : { pathLength: 0 }}
                whileInView={reduce ? undefined : { pathLength: 1 }}
                viewport={seen}
                transition={{ delay: delay + 0.15, duration: 0.6, ease: "easeOut" }}
              />
              {reduce ? null : (
                <motion.path
                  d={path}
                  stroke={d.color}
                  strokeWidth={2}
                  strokeLinecap="round"
                  fill="none"
                  strokeDasharray={`${beam} ${length + beam}`}
                  initial={{ strokeDashoffset: beam, opacity: 0 }}
                  whileInView={{ strokeDashoffset: [beam, -length], opacity: 1 }}
                  viewport={seen}
                  transition={{
                    strokeDashoffset: {
                      delay: delay + 0.75,
                      duration: 2.2,
                      ease: "easeInOut",
                      repeat: Infinity,
                      repeatDelay: 1.2 + (i % 3) * 0.4,
                    },
                    opacity: { delay: delay + 0.75, duration: 0.2 },
                  }}
                />
              )}
            </g>
          )
        })}

        <motion.g
          initial={reduce ? false : { opacity: 0, scale: 0.7 }}
          whileInView={reduce ? undefined : { opacity: 1, scale: 1 }}
          viewport={seen}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformBox: "fill-box", transformOrigin: "center" }}
        >
          <rect x={HUB.x - 32} y={HUB.y - 32} width={64} height={64} rx={14} fill="#2A2B28" />
          <svg x={HUB.x - 20} y={HUB.y - 20} width={40} height={40} viewBox="0 0 24 24" fill="#19C37D">
            <g transform="translate(12 12) skewX(-14) translate(-12 -12)">
              <rect x="1.5" y="3.2" width="21" height="7" rx="2.4" />
              <rect x="1.5" y="13.8" width="21" height="7" rx="2.4" />
            </g>
          </svg>
        </motion.g>

        {DEPTS.map((d, i) => (
          <motion.g
            key={d.label}
            initial={reduce ? false : { opacity: 0, scale: 0.85, y: 10 }}
            whileInView={reduce ? undefined : { opacity: 1, scale: 1, y: 0 }}
            viewport={seen}
            transition={{ delay: START + i * POP, duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            style={{ transformBox: "fill-box", transformOrigin: "center" }}
          >
            <rect
              x={d.x}
              y={d.y}
              width={120}
              height={54}
              rx={8}
              fill="#FFFFFF"
              stroke="#E4E4E7"
              strokeWidth={1.2}
              filter="url(#uc-card-shadow)"
            />
            <rect x={d.x + 14} y={d.y + 13} width={14} height={14} rx={3} fill={d.color} />
            <rect x={d.x + 34} y={d.y + 15} width={48} height={5} rx={2} fill="#D4D4D8" />
            <rect x={d.x + 34} y={d.y + 25} width={32} height={4} rx={2} fill="#E4E4E7" />
            <text
              x={d.x + 60}
              y={d.y + 41}
              fontSize={9}
              fontWeight={600}
              fill={d.color}
              textAnchor="middle"
              style={{ fontFamily: "DM Sans, system-ui" }}
            >
              {d.label}
            </text>
            <motion.circle
              cx={d.x + 110}
              cy={d.y + 10}
              r={4}
              fill="#19C37D"
              animate={reduce ? undefined : { opacity: [1, 0.45, 1] }}
              transition={{ duration: 1.8 + (i % 3) * 0.2, repeat: Infinity, ease: "easeInOut", delay: i * 0.3 }}
            />
          </motion.g>
        ))}
      </svg>
    </figure>
  )
}
