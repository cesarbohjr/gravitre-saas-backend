"use client"

/**
 * "Your org, Mutual consent, Partner org" diagram from the Federation design
 * (p17), ported as JSX. Colours come from the kit's --gs-* tokens so it reads
 * in light and dark; the moving dot is skipped for reduced motion.
 */
import { useEffect, useState } from "react"

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return
    const query = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setReduced(query.matches)
    update()
    query.addEventListener?.("change", update)
    return () => query.removeEventListener?.("change", update)
  }, [])
  return reduced
}

function Building({ x }: { x: number }) {
  // Building glyph from the design, offset to each box.
  const d = `M${x + 26} 88V62h26v26M${x + 32} 68h4M${x + 42} 68h4M${x + 32} 76h4M${x + 42} 76h4M${x + 36} 88v-6h6v6`
  return <path d={d} stroke="var(--gs-ink-3)" strokeWidth={1.8} fill="none" strokeLinecap="round" />
}

export function FederationConsentDiagram() {
  const reduced = useReducedMotion()
  return (
    <svg
      viewBox="0 0 420 150"
      width="100%"
      style={{ maxWidth: 460, display: "block" }}
      role="img"
      aria-label="Your org and a partner org connected through mutual consent"
    >
      <rect x={0} y={0} width={420} height={150} rx={16} fill="var(--gs-tile)" />
      <g>
        <rect x={30} y={42} width={78} height={66} rx={14} fill="var(--gs-card)" stroke="var(--gs-border)" />
        <Building x={30} />
        <text x={69} y={128} textAnchor="middle" fontSize={12} fill="var(--gs-ink-3)" fontFamily="inherit">
          Your org
        </text>
      </g>
      <g>
        <rect x={312} y={42} width={78} height={66} rx={14} fill="var(--gs-card)" stroke="var(--gs-border)" />
        <Building x={312} />
        <text x={351} y={128} textAnchor="middle" fontSize={12} fill="var(--gs-ink-3)" fontFamily="inherit">
          Partner org
        </text>
      </g>
      <path d="M112 75 H 308" stroke="var(--gs-off)" strokeWidth={2} strokeDasharray="5 6" className="gs-flow2" />
      {reduced ? (
        <circle cx={160} cy={75} r={5} fill="var(--gs-green-bright)" />
      ) : (
        <circle r={5} fill="var(--gs-green-bright)">
          <animateMotion dur="3.2s" repeatCount="indefinite" path="M112 75 H 308" />
        </circle>
      )}
      <circle cx={210} cy={75} r={20} fill="var(--gs-card)" stroke="var(--gs-green-ring)" strokeWidth={2} />
      <path
        d="M210 64l-8 3v6c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10v-6z"
        fill="var(--gs-green-bg)"
        stroke="var(--gs-green)"
        strokeWidth={1.6}
      />
      <path d="m206 74 3 3 5-5" stroke="var(--gs-green)" strokeWidth={1.8} fill="none" strokeLinecap="round" />
      <text x={210} y={116} textAnchor="middle" fontSize={12} fill="var(--gs-ink-2)" fontFamily="inherit">
        Mutual consent
      </text>
    </svg>
  )
}
