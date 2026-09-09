"use client"

/**
 * GravitreFloatingWorkspace — Phase 2 of the "Gravitre AI Agent Workspace"
 * redesign. The Float window shell.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6 phase row 2, and the Phase 0 prototype
 * (`apps/web/app/dev/ai-workspace-preview/_components/ai-workspace-prototype.tsx`),
 * whose drag-chrome pattern this reuses verbatim (native `framer-motion`
 * `drag`, `dragListener={false}` + `dragControls` started only from
 * pointer-down on the header, `dragElastic={0}`, `dragMomentum={false}`,
 * viewport-clamped `dragConstraints`).
 *
 * This component is intentionally "dumb": it owns window chrome (header,
 * presence pill, drag, minimize-to-helper) and a fixed default size, and
 * renders whatever `children` it's given. It has no opinion about what
 * conversation is inside it — that's the caller's job (see
 * `apps/web/app/ai/_components/ai-workspace-float-bridge.tsx`, the only
 * current caller). This keeps the shell trivially testable in isolation and
 * keeps "is this really the same conversation" entirely a question about
 * what props the caller passes in, not about this file.
 *
 * Phase 2 scope was drag-only (position), fixed default size, no resize
 * handle — "Resize is explicitly Phase 3 per the architecture doc's phase
 * table." Phase 3 adds resize below (B5): a custom `useWindowResize`
 * pointer-event hook (no `react-rnd`), a corner handle using the approved
 * Lucide `GripVertical` exception, and keyboard-operable arrow-key
 * step-resize (B9). Phase 3 also adds an "Expand" header control that
 * transitions to `GravitreAIWorkspaceShell`'s Expanded mode — see
 * `ai-workspace-shell-bridge.tsx` and `ai-workspace.tsx`'s wiring.
 *
 * Portal-rendered to `document.body` (not a CSS-only `fixed`) so window
 * position is never affected by an ancestor establishing a new containing
 * block (`transform`/`filter`/etc. anywhere in the per-page `AppShell` tree)
 * — the same reason Radix/Headless UI overlays portal by default.
 *
 * Not a modal by construction: no backdrop, no focus trap, `role="region"`
 * not `role="dialog"` — matches architecture doc Part B1/B9 (Float has no
 * modal semantics; only Fullscreen mode does — verified unchanged by
 * `__tests__/gravitre/ai-floating-workspace.test.ts`).
 */

import { useCallback, useEffect, useMemo, useState, type PointerEvent, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { motion, useDragControls, useReducedMotion } from "framer-motion"
import { Expand, GripVertical, Minimize2 } from "lucide-react"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"
import { useWindowResize, type WindowSize } from "@/hooks/use-window-resize"

/** Reuses the Phase 0 prototype's exact default Float size. */
export const GRAVITRE_FLOAT_DEFAULT_SIZE: WindowSize = { width: 520, height: 560 }

/**
 * Phase 3 resize clamps (B5). Min matches the Phase 0 prototype's own
 * `FLOAT_MIN` constant verbatim (400x420 — inside this task's requested
 * "~380-420px width, ~420px height" range). Max is a deliberately-chosen,
 * viewport-independent ceiling well short of Expanded territory (Expanded
 * is ~80-90% of viewport, typically 1000px+ wide on a laptop) — 720x760 —
 * so growing Float by hand never visually collides with what "Expand"
 * already does explicitly. The render below additionally clamps against
 * the live viewport so the window can never be dragged/resized off-screen.
 */
export const GRAVITRE_FLOAT_MIN_SIZE: WindowSize = { width: 400, height: 420 }
export const GRAVITRE_FLOAT_MAX_SIZE: WindowSize = { width: 720, height: 760 }

export interface GravitreFloatingWorkspaceProps {
  presence: GravitreHelperPresence
  /** Returns the workspace to Helper presentation mode. */
  onClose: () => void
  /** Transitions to Expanded mode (GravitreAIWorkspaceShell). Omitted →
   * no Expand button renders (keeps this shell usable standalone in tests). */
  onExpand?: () => void
  children: ReactNode
}

export function GravitreFloatingWorkspace({ presence, onClose, onExpand, children }: GravitreFloatingWorkspaceProps) {
  const dragControls = useDragControls()
  const reduceMotion = useReducedMotion()
  const [viewport, setViewport] = useState<{ width: number; height: number } | null>(null)
  const [size, setSize] = useState<WindowSize>(GRAVITRE_FLOAT_DEFAULT_SIZE)

  useEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

  const maxSize = useMemo<WindowSize>(() => {
    if (!viewport) return GRAVITRE_FLOAT_MAX_SIZE
    return {
      width: Math.max(GRAVITRE_FLOAT_MIN_SIZE.width, Math.min(GRAVITRE_FLOAT_MAX_SIZE.width, viewport.width - 40)),
      height: Math.max(GRAVITRE_FLOAT_MIN_SIZE.height, Math.min(GRAVITRE_FLOAT_MAX_SIZE.height, viewport.height - 40)),
    }
  }, [viewport])

  const { onPointerDown: onResizePointerDown, onKeyDown: onResizeKeyDown } = useWindowResize({
    size,
    min: GRAVITRE_FLOAT_MIN_SIZE,
    max: maxSize,
    onResize: setSize,
  })

  const onHeaderPointerDown = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      // Never start a drag from an interactive control inside the header —
      // architecture doc item 22: drag must not swallow button clicks.
      const target = event.target as HTMLElement
      if (target.closest("button,a,input,textarea")) return
      dragControls.start(event)
    },
    [dragControls],
  )

  if (typeof document === "undefined" || !viewport) return null

  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]

  return createPortal(
    <motion.div
      drag
      dragListener={false}
      dragControls={dragControls}
      dragMomentum={false}
      dragElastic={0}
      dragConstraints={{
        left: 8,
        right: Math.max(8, viewport.width - size.width - 8),
        top: 8,
        bottom: Math.max(8, viewport.height - size.height - 8),
      }}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
      transition={{ duration: reduceMotion ? 0.01 : 0.18, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto fixed bottom-5 left-5 z-[85] flex flex-col overflow-hidden rounded-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)] shadow-2xl"
      style={{ width: size.width, height: size.height }}
      data-gravitre-float-workspace=""
      role="region"
      aria-label="Gravitre AI"
    >
      <div
        onPointerDown={onHeaderPointerDown}
        data-window-drag-handle=""
        className="flex cursor-grab select-none items-center justify-between border-b border-divide px-3 py-2.5 active:cursor-grabbing"
      >
        <div className="flex min-w-0 items-center gap-2">
          <GripVertical className="h-3.5 w-3.5 text-[color:var(--g-text-muted)]" aria-hidden />
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
            <NucleoAgent className="h-3.5 w-3.5" />
          </span>
          <p className="truncate text-xs font-semibold text-[color:var(--g-text-primary)]">Gravitre AI</p>
          <span
            className={cn(
              "ml-1 flex items-center gap-1 rounded-full bg-[color:var(--g-surface-2)] px-1.5 py-0.5 text-[10px] font-medium",
              copy.tone,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", GRAVITRE_HELPER_PRESENCE_DOT[presence])} aria-hidden />
            {copy.label}
          </span>
        </div>
        <div className="flex items-center gap-0.5">
          {onExpand ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label="Expand"
              onClick={onExpand}
            >
              <Expand className="h-3.5 w-3.5" />
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Minimize to helper"
            onClick={onClose}
          >
            <Minimize2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
      {/*
        Resize handle (B5/B9). `role="slider"` isn't a great fit for 2D
        resize and neither is `separator` in the strict 1D-splitter sense,
        but `separator` + an explicit `aria-label`/`aria-valuetext` is the
        same pragmatic choice the Phase 0 prototype made — a real,
        documented trade-off, not an oversight. Keyboard-operable via
        `onResizeKeyDown` (arrow keys, Shift = coarser step) — see
        `useWindowResize`.
      */}
      <div
        role="separator"
        aria-label="Resize Gravitre AI window"
        aria-valuetext={`${Math.round(size.width)} by ${Math.round(size.height)} pixels`}
        tabIndex={0}
        onPointerDown={onResizePointerDown}
        onKeyDown={onResizeKeyDown}
        data-gravitre-float-resize-handle=""
        className="absolute bottom-0.5 right-0.5 flex h-4 w-4 cursor-nwse-resize items-center justify-center rounded-sm text-[color:var(--g-text-muted)]/60 hover:text-[color:var(--g-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40"
      >
        <GripVertical className="h-3 w-3 rotate-45" aria-hidden />
      </div>
    </motion.div>,
    document.body,
  )
}
