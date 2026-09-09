"use client"

/**
 * useWindowResize — Phase 3 of the "Gravitre AI Agent Workspace" redesign
 * (B5: drag/resize recommendation, now in scope — resize was explicitly
 * deferred from Phase 2, see `ai-floating-workspace.tsx`'s Phase 2 file
 * header: "Resize is explicitly Phase 3 per the architecture doc's phase
 * table.")
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B5: "build a small custom `useWindowResize` pointer-event hook
 * (clamped to the min/max dimensions ...) rather than adding `react-rnd` as
 * a new dependency." `react-rnd` is confirmed absent from package.json and
 * intentionally not added here.
 *
 * Pointer-move handling is throttled to `requestAnimationFrame` (B10
 * performance guidance — "resize-handle pointer deltas throttled to
 * requestAnimationFrame, not per-pixel setState"): every native
 * `pointermove` updates a pending-size ref, but `onResize` (the caller's
 * `setState`) is only invoked once per animation frame.
 *
 * Also exposes a keyboard-operable path (`onKeyDown`, arrow-key step-resize)
 * per B9 — "Resize handles get keyboard-operable equivalents ... not
 * mouse-only."
 */

import { useCallback, useRef } from "react"
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react"

export interface WindowSize {
  width: number
  height: number
}

export interface UseWindowResizeOptions {
  /** Current controlled size — read via a ref internally so pointer-move
   * handlers always see the latest value without re-subscribing. */
  size: WindowSize
  min: WindowSize
  max: WindowSize
  onResize: (size: WindowSize) => void
  /** Keyboard arrow-key step, in px. Default 16 — matches the app's usual
   * "medium" spacing step, not a magic number. */
  step?: number
  /** Shift+Arrow multiplier for a coarser keyboard step. */
  shiftMultiplier?: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function useWindowResize({
  size,
  min,
  max,
  onResize,
  step = 16,
  shiftMultiplier = 3,
}: UseWindowResizeOptions) {
  // Always-fresh refs so the pointermove/pointerup listeners (added once per
  // drag gesture, not per render) never close over a stale size/bounds.
  const sizeRef = useRef(size)
  sizeRef.current = size
  const boundsRef = useRef({ min, max })
  boundsRef.current = { min, max }

  const dragRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null)
  const rafRef = useRef<number | null>(null)
  const pendingRef = useRef<WindowSize | null>(null)
  const onResizeRef = useRef(onResize)
  onResizeRef.current = onResize

  const flush = useCallback(() => {
    rafRef.current = null
    const pending = pendingRef.current
    pendingRef.current = null
    if (pending) onResizeRef.current(pending)
  }, [])

  const schedule = useCallback(
    (next: WindowSize) => {
      pendingRef.current = next
      if (rafRef.current == null) {
        rafRef.current = requestAnimationFrame(flush)
      }
    },
    [flush],
  )

  const onPointerDown = useCallback(
    (event: ReactPointerEvent) => {
      event.preventDefault()
      dragRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        startW: sizeRef.current.width,
        startH: sizeRef.current.height,
      }

      const onMove = (moveEvent: PointerEvent) => {
        const drag = dragRef.current
        if (!drag) return
        const { min: currentMin, max: currentMax } = boundsRef.current
        const dx = moveEvent.clientX - drag.startX
        const dy = moveEvent.clientY - drag.startY
        schedule({
          width: clamp(drag.startW + dx, currentMin.width, currentMax.width),
          height: clamp(drag.startH + dy, currentMin.height, currentMax.height),
        })
      }

      const onUp = () => {
        dragRef.current = null
        window.removeEventListener("pointermove", onMove)
        window.removeEventListener("pointerup", onUp)
        // Flush any pending rAF-throttled update immediately on release so
        // the final size is never dropped by frame timing.
        if (rafRef.current != null) {
          cancelAnimationFrame(rafRef.current)
          flush()
        }
      }

      window.addEventListener("pointermove", onMove)
      window.addEventListener("pointerup", onUp)
    },
    [schedule, flush],
  )

  const onKeyDown = useCallback(
    (event: ReactKeyboardEvent) => {
      const delta = event.shiftKey ? step * shiftMultiplier : step
      let dw = 0
      let dh = 0
      switch (event.key) {
        case "ArrowRight":
          dw = delta
          break
        case "ArrowLeft":
          dw = -delta
          break
        case "ArrowDown":
          dh = delta
          break
        case "ArrowUp":
          dh = -delta
          break
        default:
          return
      }
      event.preventDefault()
      const { min: currentMin, max: currentMax } = boundsRef.current
      onResizeRef.current({
        width: clamp(sizeRef.current.width + dw, currentMin.width, currentMax.width),
        height: clamp(sizeRef.current.height + dh, currentMin.height, currentMax.height),
      })
    },
    [step, shiftMultiplier],
  )

  return { onPointerDown, onKeyDown }
}
