"use client"

import type { PacketKind } from "./types"

const KIND_MID: Record<PacketKind, string> = {
  signal: "var(--info)",
  action: "var(--brand)",
  learn: "var(--g-intelligence)",
}

/**
 * Path TRACE in the Nodus wiring: a --color-line hairline with a short beam
 * that keeps travelling toward the core. An active edge runs a faster beam in
 * its packet colour; learned edges keep a faint brand hairline.
 */
export function GravitreSignalPath({
  d,
  activeKind = null,
  muted = false,
  reduced = false,
  learned = false,
  delay = 0,
}: {
  d: string
  activeKind?: PacketKind | null
  muted?: boolean
  reduced?: boolean
  learned?: boolean
  /** Seconds to offset the idle beam so the wires don't pulse in sync. */
  delay?: number
}) {
  const active = activeKind != null

  return (
    <g opacity={muted ? 0.35 : 1}>
      <style>{`
        @keyframes dn-beam {
          0% { stroke-dashoffset: 0.3; opacity: 0 }
          8% { opacity: 1 }
          62% { opacity: 1 }
          71%, 100% { stroke-dashoffset: -1; opacity: 0 }
        }
      `}</style>
      <path d={d} fill="none" stroke="var(--color-line)" strokeWidth={1.5} strokeLinecap="round" />
      {learned && !active ? (
        <path d={d} fill="none" stroke="var(--brand)" strokeWidth={1.5} strokeLinecap="round" opacity={0.35} />
      ) : null}
      {reduced ? (
        active ? (
          <path d={d} fill="none" stroke={KIND_MID[activeKind]} strokeWidth={1.5} strokeLinecap="round" />
        ) : null
      ) : (
        <path
          key={active ? `active-${activeKind}` : "idle"}
          d={d}
          fill="none"
          pathLength={1}
          stroke={active ? KIND_MID[activeKind] : "var(--brand)"}
          strokeWidth={active ? 2 : 1.5}
          strokeLinecap="round"
          strokeDasharray="0.3 1.3"
          style={{
            opacity: 0,
            animation: active ? "dn-beam 1.6s linear infinite" : `dn-beam 7s linear ${delay}s infinite`,
          }}
        />
      )}
    </g>
  )
}
