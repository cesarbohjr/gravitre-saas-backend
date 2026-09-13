"use client"

/**
 * Phase F — WebGL2 central Intelligence Core aura (raw WebGL2, no three.js).
 * Decorative state-driven glow behind CoreHubNode; does not invent topology.
 *
 * Perf / a11y: pauses offscreen, static frame when prefers-reduced-motion,
 * tears down on unmount. Falls back to nothing if WebGL2 unavailable.
 */

import { useEffect, useRef } from "react"
import type { IntelligenceCoreVisualState } from "@/lib/api"
import { cn } from "@/lib/utils"

type Props = {
  state: IntelligenceCoreVisualState
  className?: string
  /** 0–1 activity multiplier from live core metrics. */
  activity?: number
}

const STATE_RGB: Record<IntelligenceCoreVisualState, [number, number, number]> = {
  idle: [0.55, 0.62, 0.58],
  "flow-inward": [0.2, 0.55, 0.95],
  trace: [0.09, 0.64, 0.45],
  "pending-approval": [0.85, 0.47, 0.04],
  resolved: [0.09, 0.64, 0.45],
  "low-confidence": [0.58, 0.64, 0.72],
}

const STATE_SPEED: Record<IntelligenceCoreVisualState, number> = {
  idle: 0.35,
  "flow-inward": 0.9,
  trace: 1.2,
  "pending-approval": 0.75,
  resolved: 0.5,
  "low-confidence": 0.25,
}

export function CoreHubWebGL({ state, className, activity = 0.35 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvasEl = canvasRef.current
    if (!canvasEl) return

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const glCtx = canvasEl.getContext("webgl2", {
      alpha: true,
      antialias: true,
      powerPreference: "low-power",
    })
    if (!glCtx) return
    const gl: WebGL2RenderingContext = glCtx
    const canvas: HTMLCanvasElement = canvasEl

    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    let width = 0
    let height = 0
    let raf = 0
    let visible = true
    let disposed = false
    let t = 0

    const vsSource = `#version 300 es
      in vec2 a_pos;
      in float a_size;
      in float a_alpha;
      out float v_alpha;
      uniform vec2 u_res;
      void main() {
        vec2 clip = (a_pos / u_res) * 2.0 - 1.0;
        clip.y = -clip.y;
        gl_Position = vec4(clip, 0.0, 1.0);
        gl_PointSize = a_size;
        v_alpha = a_alpha;
      }`
    const fsSource = `#version 300 es
      precision mediump float;
      uniform vec3 u_color;
      in float v_alpha;
      out vec4 outColor;
      void main() {
        vec2 c = gl_PointCoord - vec2(0.5);
        float d = length(c);
        float a = smoothstep(0.5, 0.08, d) * v_alpha;
        outColor = vec4(u_color, a);
      }`

    function compile(type: number, src: string) {
      const shader = gl.createShader(type)
      if (!shader) throw new Error("shader")
      gl.shaderSource(shader, src)
      gl.compileShader(shader)
      return shader
    }

    const prog = gl.createProgram()
    if (!prog) return
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, vsSource))
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, fsSource))
    gl.linkProgram(prog)
    gl.useProgram(prog)

    const orbitCount = 28
    const positions = new Float32Array(orbitCount * 2)
    const sizes = new Float32Array(orbitCount)
    const alphas = new Float32Array(orbitCount)

    const posBuf = gl.createBuffer()
    const sizeBuf = gl.createBuffer()
    const alphaBuf = gl.createBuffer()
    if (!posBuf || !sizeBuf || !alphaBuf) return

    const aPos = gl.getAttribLocation(prog, "a_pos")
    const aSize = gl.getAttribLocation(prog, "a_size")
    const aAlpha = gl.getAttribLocation(prog, "a_alpha")
    const uRes = gl.getUniformLocation(prog, "u_res")
    const uColor = gl.getUniformLocation(prog, "u_color")

    function resize() {
      const rect = canvas.getBoundingClientRect()
      width = Math.max(1, Math.floor(rect.width * dpr))
      height = Math.max(1, Math.floor(rect.height * dpr))
      canvas.width = width
      canvas.height = height
      gl.viewport(0, 0, width, height)
    }

    function paint() {
      if (disposed) return
      if (!visible) {
        if (!reduceMotion) raf = requestAnimationFrame(paint)
        return
      }

      if (!reduceMotion) t += 0.016 * STATE_SPEED[state]

      const cx = width * 0.5
      const cy = height * 0.5
      const baseRadius = Math.min(width, height) * (0.22 + activity * 0.08)
      const [r, g, b] = STATE_RGB[state]

      for (let i = 0; i < orbitCount; i++) {
        const angle = (i / orbitCount) * Math.PI * 2 + t * (0.6 + (i % 3) * 0.15)
        const wobble = reduceMotion ? 0 : Math.sin(t * 1.4 + i) * 0.06
        const radius = baseRadius * (0.75 + wobble + (i % 5) * 0.04)
        positions[i * 2] = cx + Math.cos(angle) * radius
        positions[i * 2 + 1] = cy + Math.sin(angle) * radius
        sizes[i] = (2.5 + (i % 4) * 0.8 + activity * 2) * dpr
        alphas[i] = 0.25 + (i % 3) * 0.12 + activity * 0.35
      }

      // Inner core glow points
      for (let i = 0; i < 6; i++) {
        const idx = orbitCount - 6 + i
        const angle = (i / 6) * Math.PI * 2
        const innerR = baseRadius * 0.18
        positions[idx * 2] = cx + Math.cos(angle + t) * innerR
        positions[idx * 2 + 1] = cy + Math.sin(angle + t) * innerR
        sizes[idx] = (5 + activity * 4) * dpr
        alphas[idx] = 0.55 + activity * 0.25
      }

      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.enable(gl.BLEND)
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)

      gl.uniform2f(uRes, width, height)
      gl.uniform3f(uColor, r, g, b)

      gl.bindBuffer(gl.ARRAY_BUFFER, posBuf)
      gl.bufferData(gl.ARRAY_BUFFER, positions, gl.DYNAMIC_DRAW)
      gl.enableVertexAttribArray(aPos)
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, sizeBuf)
      gl.bufferData(gl.ARRAY_BUFFER, sizes, gl.DYNAMIC_DRAW)
      gl.enableVertexAttribArray(aSize)
      gl.vertexAttribPointer(aSize, 1, gl.FLOAT, false, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, alphaBuf)
      gl.bufferData(gl.ARRAY_BUFFER, alphas, gl.DYNAMIC_DRAW)
      gl.enableVertexAttribArray(aAlpha)
      gl.vertexAttribPointer(aAlpha, 1, gl.FLOAT, false, 0, 0)

      gl.drawArrays(gl.POINTS, 0, orbitCount)

      if (!reduceMotion) raf = requestAnimationFrame(paint)
    }

    resize()
    paint()

    const onResize = () => {
      resize()
      if (reduceMotion) paint()
    }
    window.addEventListener("resize", onResize)

    const io = new IntersectionObserver(
      (entries) => {
        visible = entries.some((e) => e.isIntersecting)
      },
      { threshold: 0.05 },
    )
    io.observe(canvas)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", onResize)
      io.disconnect()
      const lose = gl.getExtension("WEBGL_lose_context")
      lose?.loseContext()
    }
  }, [state, activity])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={cn(
        "pointer-events-none absolute left-1/2 top-1/2 z-0 h-[min(280px,42vw)] w-[min(280px,42vw)] -translate-x-1/2 -translate-y-1/2",
        className,
      )}
    />
  )
}
