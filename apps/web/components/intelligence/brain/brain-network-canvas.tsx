"use client"

import { useEffect, useRef } from "react"
import type { BrainLayer, BrainTone } from "@/lib/intelligence/brain-model"

/** Horizontal padding of the first and last layer, in % of the width. Labels use the same value. */
export const BRAIN_LAYER_PAD = 10

export function brainLayerX(index: number, count: number): number {
  if (count <= 1) return 50
  return BRAIN_LAYER_PAD + (index * (100 - BRAIN_LAYER_PAD * 2)) / (count - 1)
}

const TONE_VAR: Record<BrainTone, string> = {
  neutral: "--g-text-muted",
  intelligence: "--g-intelligence",
  brand: "--g-brand",
  approval: "--g-approval",
  danger: "--g-danger",
}

type RGB = [number, number, number]

/** Resolve any CSS color (hex, rgb, oklch, var chains) to RGB by painting one pixel. */
function readColor(el: Element, cssVar: string, probe: CanvasRenderingContext2D): RGB {
  const raw = getComputedStyle(el).getPropertyValue(cssVar).trim() || "#808080"
  probe.clearRect(0, 0, 1, 1)
  probe.fillStyle = "#808080"
  probe.fillStyle = raw
  probe.fillRect(0, 0, 1, 1)
  const [r, g, b] = probe.getImageData(0, 0, 1, 1).data
  return [r, g, b]
}

const rgba = ([r, g, b]: RGB, a: number) => `rgba(${r},${g},${b},${Math.max(0, Math.min(1, a))})`

type Node = { x: number; y: number; act: number; target: number }
type Particle = { li: number; from: Node; to: Node; p: number; spd: number; color: RGB; size: number }
type Flash = { a: Node; b: Node; age: number; max: number }

/**
 * Animated layered network, adapted from an ML training view. Signals flow
 * forward from sources to forecasts, feedback flows back, and amber flashes
 * mark connections being re-weighted by what Gravitre learned. The rate of all
 * three follows real activity; the shape follows real counts per layer.
 */
export function BrainNetworkCanvas({
  layers,
  activity,
  paused,
  speed,
  reducedMotion,
  className,
}: {
  layers: BrainLayer[]
  activity: number
  paused: boolean
  speed: number
  reducedMotion: boolean
  className?: string
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const live = useRef({ paused, speed, activity, reducedMotion })
  live.current = { paused, speed, activity, reducedMotion }
  const shape = layers.map((l) => `${l.id}:${l.nodes}:${l.tone}:${l.count == null ? "n" : l.count > 0 ? "y" : "z"}`).join("|")

  useEffect(() => {
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    if (!wrap || !canvas) return
    const ctx = canvas.getContext("2d")
    const probeCanvas = document.createElement("canvas")
    probeCanvas.width = probeCanvas.height = 1
    const probe = probeCanvas.getContext("2d", { willReadFrequently: true })
    if (!ctx || !probe) return

    const spec = layers.map((l) => ({ nodes: l.nodes, tone: l.tone, empty: !l.count }))
    let width = 0
    let height = 0
    let dpr = 1
    let nodes: Node[][] = []
    let particles: Particle[] = []
    let flashes: Flash[] = []
    let colors = { layer: [] as RGB[], grid: [0, 0, 0] as RGB, edge: [0, 0, 0] as RGB, forward: [0, 0, 0] as RGB, back: [0, 0, 0] as RGB, flash: [0, 0, 0] as RGB }
    let tickCount = 0
    let lastTick = 0
    let raf = 0
    let visible = true

    const readColors = () => {
      colors = {
        layer: spec.map((s) => readColor(wrap, TONE_VAR[s.tone], probe)),
        grid: readColor(wrap, "--g-border-subtle", probe),
        edge: readColor(wrap, "--g-border-default", probe),
        forward: readColor(wrap, "--g-brand", probe),
        back: readColor(wrap, "--g-intelligence", probe),
        flash: readColor(wrap, "--g-approval", probe),
      }
    }

    const layout = () => {
      width = wrap.clientWidth
      height = wrap.clientHeight
      dpr = window.devicePixelRatio || 1
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      // Leave room above for the HTML layer labels and below for the legend.
      const top = Math.max(64, height * 0.18)
      const bottom = height - (width < 640 ? 76 : 56)
      nodes = spec.map((s, li) => {
        const x = (brainLayerX(li, spec.length) / 100) * width
        const step = (bottom - top) / (s.nodes + 1)
        return Array.from({ length: s.nodes }, (_, ni) => {
          const prev = nodes[li]?.[ni]
          const act = prev?.act ?? (s.empty ? 0.15 : 0.35 + Math.random() * 0.4)
          return { x, y: top + step * (ni + 1), act, target: act }
        })
      })
      particles = []
      flashes = []
    }

    const pick = (layer: Node[]) => layer[Math.floor(Math.random() * layer.length)]

    const tick = () => {
      tickCount += 1
      const { activity: a } = live.current
      spec.forEach((s, li) => {
        for (const n of nodes[li] ?? []) n.target = s.empty ? 0.12 + Math.random() * 0.1 : 0.2 + Math.random() * (0.45 + a * 0.35)
      })
      const forwardWaves = 1 + Math.round(a * 2)
      for (let w = 0; w < forwardWaves; w++) {
        for (let li = 0; li < nodes.length - 1; li++) {
          if (spec[li].empty && Math.random() < 0.7) continue
          particles.push({ li, from: pick(nodes[li]), to: pick(nodes[li + 1]), p: -w * 0.12, spd: 0.012 + Math.random() * 0.01, color: colors.forward, size: 2 + Math.random() })
        }
      }
      if (tickCount % 3 === 0) {
        for (let li = nodes.length - 1; li > 0; li--) {
          particles.push({ li, from: pick(nodes[li]), to: pick(nodes[li - 1]), p: 0, spd: 0.009 + Math.random() * 0.007, color: colors.back, size: 1.6 + Math.random() * 0.8 })
        }
        const count = 2 + Math.round(a * 4)
        for (let i = 0; i < count; i++) {
          const li = Math.floor(Math.random() * (nodes.length - 1))
          flashes.push({ a: pick(nodes[li]), b: pick(nodes[li + 1]), age: 0, max: 40 })
        }
      }
    }

    const draw = (animate: boolean) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)

      ctx.strokeStyle = rgba(colors.grid, 0.55)
      ctx.lineWidth = 0.5
      const gs = 32
      ctx.beginPath()
      for (let x = gs; x < width; x += gs) {
        ctx.moveTo(x, 0)
        ctx.lineTo(x, height)
      }
      for (let y = gs; y < height; y += gs) {
        ctx.moveTo(0, y)
        ctx.lineTo(width, y)
      }
      ctx.stroke()

      for (let li = 0; li < nodes.length - 1; li++) {
        for (const s of nodes[li]) {
          for (const d of nodes[li + 1]) {
            const act = (s.act + d.act) / 2
            ctx.strokeStyle = rgba(colors.edge, 0.18 + act * 0.5)
            ctx.lineWidth = 0.6
            ctx.beginPath()
            ctx.moveTo(s.x, s.y)
            ctx.lineTo(d.x, d.y)
            ctx.stroke()
          }
        }
      }

      flashes = flashes.filter((f) => f.age < f.max)
      for (const f of flashes) {
        ctx.strokeStyle = rgba(colors.flash, (1 - f.age / f.max) * 0.75)
        ctx.lineWidth = 1.4
        ctx.beginPath()
        ctx.moveTo(f.a.x, f.a.y)
        ctx.lineTo(f.b.x, f.b.y)
        ctx.stroke()
        if (animate) f.age += live.current.speed
      }

      particles = particles.filter((p) => p.p < 1)
      for (const p of particles) {
        if (animate) p.p = Math.min(1, p.p + p.spd * live.current.speed)
        if (p.p <= 0) continue
        const x = p.from.x + (p.to.x - p.from.x) * p.p
        const y = p.from.y + (p.to.y - p.from.y) * p.p
        const t0 = Math.max(0, p.p - 0.2)
        const x0 = p.from.x + (p.to.x - p.from.x) * t0
        const y0 = p.from.y + (p.to.y - p.from.y) * t0
        const trail = ctx.createLinearGradient(x0, y0, x, y)
        trail.addColorStop(0, rgba(p.color, 0))
        trail.addColorStop(1, rgba(p.color, 0.8))
        ctx.strokeStyle = trail
        ctx.lineWidth = p.size * 0.6
        ctx.beginPath()
        ctx.moveTo(x0, y0)
        ctx.lineTo(x, y)
        ctx.stroke()
        ctx.beginPath()
        ctx.arc(x, y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = rgba(p.color, 1)
        ctx.shadowColor = rgba(p.color, 0.9)
        ctx.shadowBlur = 8
        ctx.fill()
        ctx.shadowBlur = 0
      }

      nodes.forEach((layer, li) => {
        const c = colors.layer[li] ?? colors.edge
        const empty = spec[li]?.empty
        for (const n of layer) {
          if (animate) n.act += (n.target - n.act) * 0.06
          const r = 6
          const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 2.6)
          glow.addColorStop(0, rgba(c, n.act * 0.35))
          glow.addColorStop(1, rgba(c, 0))
          ctx.fillStyle = glow
          ctx.beginPath()
          ctx.arc(n.x, n.y, r * 2.6, 0, Math.PI * 2)
          ctx.fill()
          ctx.setLineDash(empty ? [2, 2] : [])
          ctx.strokeStyle = rgba(c, 0.35 + n.act * 0.65)
          ctx.lineWidth = 1.3
          ctx.beginPath()
          ctx.arc(n.x, n.y, r, 0, Math.PI * 2)
          ctx.stroke()
          ctx.setLineDash([])
          ctx.fillStyle = rgba(c, empty ? 0.1 : 0.25 + n.act * 0.65)
          ctx.beginPath()
          ctx.arc(n.x, n.y, r * 0.6, 0, Math.PI * 2)
          ctx.fill()
        }
      })
    }

    const frame = (ts: number) => {
      raf = 0
      const { paused: isPaused, speed: s, activity: a, reducedMotion: still } = live.current
      if (still || !visible) {
        draw(false)
        return
      }
      const interval = (1500 - a * 900) / s
      if (!isPaused && ts - lastTick > interval) {
        lastTick = ts
        tick()
      }
      draw(!isPaused)
      raf = requestAnimationFrame(frame)
    }
    const start = () => {
      if (!raf) raf = requestAnimationFrame(frame)
    }

    readColors()
    layout()
    if (!live.current.reducedMotion) {
      // Seed a few signals so the first paint already shows flow.
      tick()
      tick()
    }
    draw(false)
    start()

    const resize = new ResizeObserver(() => {
      layout()
      draw(false)
      start()
    })
    resize.observe(wrap)
    const theme = new MutationObserver(() => {
      readColors()
      draw(false)
      start()
    })
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] })
    const seen = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true
      if (visible) start()
    })
    seen.observe(wrap)
    const onVisibility = () => {
      visible = !document.hidden
      if (visible) start()
    }
    document.addEventListener("visibilitychange", onVisibility)
    canvas.addEventListener("brain:wake", start)

    return () => {
      canvas.removeEventListener("brain:wake", start)
      if (raf) cancelAnimationFrame(raf)
      resize.disconnect()
      theme.disconnect()
      seen.disconnect()
      document.removeEventListener("visibilitychange", onVisibility)
    }
    // `shape` captures everything layout depends on; live props are read through a ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shape])

  // Restart the loop when motion settings change after a still frame.
  useEffect(() => {
    const canvas = canvasRef.current
    canvas?.dispatchEvent(new Event("brain:wake"))
  }, [paused, speed, reducedMotion])

  return (
    <div ref={wrapRef} className={className} aria-hidden>
      <canvas ref={canvasRef} className="block h-full w-full" />
    </div>
  )
}
