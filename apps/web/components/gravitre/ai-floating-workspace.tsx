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
 * Phase 2 scope: drag-only (position), fixed default size, no resize handle.
 * Resize is explicitly Phase 3 per the architecture doc's phase table.
 *
 * Portal-rendered to `document.body` (not a CSS-only `fixed`) so window
 * position is never affected by an ancestor establishing a new containing
 * block (`transform`/`filter`/etc. anywhere in the per-page `AppShell` tree)
 * — the same reason Radix/Headless UI overlays portal by default.
 *
 * Not a modal by construction: no backdrop, no focus trap, `role="region"`
 * not `role="dialog"` — matches architecture doc Part B1/B9 (Float has no
 * modal semantics; only a future Fullscreen mode would).
 */

import { useCallback, useEffect, useState, type PointerEvent, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { motion, useDragControls } from "framer-motion"
import { GripVertical, Minimize2 } from "lucide-react"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"

/** Reuses the Phase 0 prototype's exact default Float size. */
export const GRAVITRE_FLOAT_DEFAULT_SIZE = { width: 520, height: 560 }

export interface GravitreFloatingWorkspaceProps {
  presence: GravitreHelperPresence
  /** Returns the workspace to Helper presentation mode. */
  onClose: () => void
  children: ReactNode
}

export function GravitreFloatingWorkspace({ presence, onClose, children }: GravitreFloatingWorkspaceProps) {
  const dragControls = useDragControls()
  const [viewport, setViewport] = useState<{ width: number; height: number } | null>(null)

  useEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

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
        right: Math.max(8, viewport.width - GRAVITRE_FLOAT_DEFAULT_SIZE.width - 8),
        top: 8,
        bottom: Math.max(8, viewport.height - GRAVITRE_FLOAT_DEFAULT_SIZE.height - 8),
      }}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto fixed bottom-5 left-5 z-[85] flex flex-col overflow-hidden rounded-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)] shadow-2xl"
      style={{ width: GRAVITRE_FLOAT_DEFAULT_SIZE.width, height: GRAVITRE_FLOAT_DEFAULT_SIZE.height }}
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
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
    </motion.div>,
    document.body,
  )
}
