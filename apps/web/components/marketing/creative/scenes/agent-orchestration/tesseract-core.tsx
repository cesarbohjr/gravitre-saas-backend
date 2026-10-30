"use client"

import { useEffect, useRef } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"

/**
 * Orchestration core: a tesseract (4D hypercube) turning through the fourth
 * dimension around the Gravitre mark, so its projection keeps folding from
 * cube to frustum to nested cubes and back. Vertices and edges are written
 * straight to the SVG on each frame instead of through React state.
 */
const VERTS: number[][] = Array.from({ length: 16 }, (_, i) => [
  i & 1 ? 1 : -1,
  i & 2 ? 1 : -1,
  i & 4 ? 1 : -1,
  i & 8 ? 1 : -1,
])

// Two vertices share an edge when they differ in exactly one coordinate.
const EDGES: [number, number][] = []
for (let a = 0; a < 16; a++) {
  for (let bit = 1; bit < 16; bit <<= 1) {
    const b = a ^ bit
    if (a < b) EDGES.push([a, b])
  }
}

const SIZE = 240
const C = SIZE / 2
const SCALE = 54

function project(t: number) {
  const xw = t * 0.42
  const yz = t * 0.27
  const zw = t * 0.19
  const cxw = Math.cos(xw)
  const sxw = Math.sin(xw)
  const cyz = Math.cos(yz)
  const syz = Math.sin(yz)
  const czw = Math.cos(zw)
  const szw = Math.sin(zw)
  return VERTS.map(([x0, y0, z0, w0]) => {
    const x = x0 * cxw - w0 * sxw
    let w = x0 * sxw + w0 * cxw
    const y = y0 * cyz - z0 * syz
    let z = y0 * syz + z0 * cyz
    const z2 = z * czw - w * szw
    w = z * szw + w * czw
    z = z2
    const k4 = 1 / (2.4 - w)
    const x3 = x * k4
    const y3 = y * k4
    const z3 = z * k4
    const k3 = 1.9 / (2.6 - z3)
    return { x: C + x3 * k3 * SCALE * 1.6, y: C + y3 * k3 * SCALE * 1.6, depth: w }
  })
}

export function TesseractCore({ settled = false, className }: { settled?: boolean; className?: string }) {
  const reduce = useReducedMotion()
  const rootRef = useRef<SVGSVGElement>(null)
  const edgeRefs = useRef<(SVGLineElement | null)[]>([])
  const nodeRefs = useRef<(SVGCircleElement | null)[]>([])
  const inView = useInView(rootRef, { amount: 0.2 })

  useEffect(() => {
    const draw = (t: number) => {
      const pts = project(t)
      EDGES.forEach(([a, b], i) => {
        const el = edgeRefs.current[i]
        if (!el) return
        el.setAttribute("x1", pts[a].x.toFixed(2))
        el.setAttribute("y1", pts[a].y.toFixed(2))
        el.setAttribute("x2", pts[b].x.toFixed(2))
        el.setAttribute("y2", pts[b].y.toFixed(2))
        // Edges deeper in the fourth dimension fade back.
        const d = (pts[a].depth + pts[b].depth) / 2
        el.setAttribute("stroke-opacity", (0.35 + 0.45 * ((d + 1.5) / 3)).toFixed(2))
      })
      pts.forEach((p, i) => {
        const el = nodeRefs.current[i]
        if (!el) return
        el.setAttribute("cx", p.x.toFixed(2))
        el.setAttribute("cy", p.y.toFixed(2))
        el.setAttribute("r", (1.6 + 1.2 * ((p.depth + 1.5) / 3)).toFixed(2))
      })
    }

    if (reduce || !inView) {
      draw(1.1)
      return
    }
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      draw(1.1 + (now - start) / 1000)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [reduce, inView])

  const stroke = settled ? "var(--brand)" : "color-mix(in srgb, var(--g-intelligence) 55%, var(--g-border-strong))"

  return (
    <svg
      ref={rootRef}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className={cn("pointer-events-none aspect-square", className)}
      aria-hidden
    >
      {EDGES.map((_, i) => (
        <line
          key={i}
          ref={(el) => {
            edgeRefs.current[i] = el
          }}
          stroke={stroke}
          strokeWidth={1.2}
          strokeLinecap="round"
          style={{ transition: "stroke 0.6s ease" }}
        />
      ))}
      {VERTS.map((_, i) => (
        <circle
          key={i}
          ref={(el) => {
            nodeRefs.current[i] = el
          }}
          fill="#FFFFFF"
          stroke={stroke}
          strokeWidth={1.2}
          style={{ transition: "stroke 0.6s ease" }}
        />
      ))}
      <rect x={C - 18} y={C - 18} width={36} height={36} rx={9} fill="#141513" />
      <svg x={C - 11} y={C - 11} width={22} height={22} viewBox="0 0 24 24" fill="var(--brand)">
        <g transform="translate(12 12) skewX(-14) translate(-12 -12)">
          <rect x="1.5" y="3.2" width="21" height="7" rx="2.4" />
          <rect x="1.5" y="13.8" width="21" height="7" rx="2.4" />
        </g>
      </svg>
    </svg>
  )
}
