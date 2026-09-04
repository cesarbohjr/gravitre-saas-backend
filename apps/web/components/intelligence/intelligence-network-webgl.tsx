"use client"

/**
 * Decorative intelligence network — raw WebGL2 (no three.js).
 * Approved for UI 2.0 Phase 9 on /intelligence only (not app chrome).
 *
 * Perf / a11y:
 * - pauses when offscreen (IntersectionObserver)
 * - static frame when prefers-reduced-motion
 * - caps node count; tears down on unmount
 * Does not invent product claims or live backend topology.
 */

import { useEffect, useRef } from "react"
import { cn } from "@/lib/utils"

type Props = {
  className?: string
  /** Max nodes (default 40). Keep low for laptop GPUs. */
  nodeCount?: number
}

function readPrimaryRgb(el: HTMLElement): [number, number, number] {
  const styles = getComputedStyle(el)
  const raw =
    styles.getPropertyValue("--gv-voice-user").trim() ||
    styles.getPropertyValue("--primary").trim() ||
    "#16a374"
  if (raw.startsWith("#") && raw.length >= 7) {
    return [
      Number.parseInt(raw.slice(1, 3), 16) / 255,
      Number.parseInt(raw.slice(3, 5), 16) / 255,
      Number.parseInt(raw.slice(5, 7), 16) / 255,
    ]
  }
  return [0.09, 0.64, 0.45]
}

export function IntelligenceNetworkWebGL({ className, nodeCount = 40 }: Props) {
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

    const vsSource = `#version 300 es
      in vec2 a_pos;
      in float a_size;
      uniform vec2 u_res;
      void main() {
        vec2 clip = (a_pos / u_res) * 2.0 - 1.0;
        clip.y = -clip.y;
        gl_Position = vec4(clip, 0.0, 1.0);
        gl_PointSize = a_size;
      }`
    const fsSource = `#version 300 es
      precision mediump float;
      uniform vec3 u_color;
      out vec4 outColor;
      void main() {
        vec2 c = gl_PointCoord - vec2(0.5);
        float d = length(c);
        float a = smoothstep(0.5, 0.12, d);
        outColor = vec4(u_color, a * 0.8);
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

    const n = Math.max(12, Math.min(nodeCount, 64))
    const positions = new Float32Array(n * 2)
    const sizes = new Float32Array(n)
    const velocities = new Float32Array(n * 2)
    for (let i = 0; i < n; i++) {
      positions[i * 2] = Math.random()
      positions[i * 2 + 1] = Math.random()
      sizes[i] = (2.5 + Math.random() * 3.5) * dpr
      velocities[i * 2] = (Math.random() - 0.5) * 0.00025
      velocities[i * 2 + 1] = (Math.random() - 0.5) * 0.00025
    }

    const posBuf = gl.createBuffer()
    const sizeBuf = gl.createBuffer()
    if (!posBuf || !sizeBuf) return
    const aPos = gl.getAttribLocation(prog, "a_pos")
    const aSize = gl.getAttribLocation(prog, "a_size")
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

      if (!reduceMotion) {
        for (let i = 0; i < n; i++) {
          positions[i * 2] += velocities[i * 2]
          positions[i * 2 + 1] += velocities[i * 2 + 1]
          if (positions[i * 2] <= 0 || positions[i * 2] >= 1) velocities[i * 2] *= -1
          if (positions[i * 2 + 1] <= 0 || positions[i * 2 + 1] >= 1) velocities[i * 2 + 1] *= -1
          positions[i * 2] = Math.min(1, Math.max(0, positions[i * 2]))
          positions[i * 2 + 1] = Math.min(1, Math.max(0, positions[i * 2 + 1]))
        }
      }

      const px = new Float32Array(n * 2)
      for (let i = 0; i < n; i++) {
        px[i * 2] = positions[i * 2] * width
        px[i * 2 + 1] = positions[i * 2 + 1] * height
      }

      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.enable(gl.BLEND)
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA)

      const [r, g, b] = readPrimaryRgb(canvas)
      gl.uniform2f(uRes, width, height)
      gl.uniform3f(uColor, r, g, b)

      gl.bindBuffer(gl.ARRAY_BUFFER, posBuf)
      gl.bufferData(gl.ARRAY_BUFFER, px, gl.DYNAMIC_DRAW)
      gl.enableVertexAttribArray(aPos)
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)

      gl.bindBuffer(gl.ARRAY_BUFFER, sizeBuf)
      gl.bufferData(gl.ARRAY_BUFFER, sizes, gl.STATIC_DRAW)
      gl.enableVertexAttribArray(aSize)
      gl.vertexAttribPointer(aSize, 1, gl.FLOAT, false, 0, 0)

      gl.drawArrays(gl.POINTS, 0, n)

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
  }, [nodeCount])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 h-full w-full opacity-35", className)}
    />
  )
}
