"use client"

/**
 * GravitreAIWorkspaceShell — Phase 3 of the "Gravitre AI Agent Workspace"
 * redesign. The Expanded/Fullscreen window shell.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6 phase row 3 ("Expanded/Fullscreen shell"), and the Phase 0
 * prototype's `GravitreAIWorkspaceShell` (`apps/web/app/dev/
 * ai-workspace-preview/_components/ai-workspace-prototype.tsx`), whose
 * visual/structural chrome (inset-based Expanded sizing, header layout,
 * "Collapse to float"/"Exit fullscreen" affordance) this reuses, wired to
 * real state instead of mock state.
 *
 * Like `GravitreFloatingWorkspace` (Phase 2), this component is "dumb": it
 * owns window chrome, panel collapse toggles, focus-trap wiring, and the
 * Escape key — not conversation state. See
 * `apps/web/app/ai/_components/ai-workspace-shell-bridge.tsx` for the only
 * current caller, which supplies the real Left/Center/Right content.
 *
 * Accessibility (B9):
 *  - Expanded: `role="region"`, `aria-label`, NO `aria-modal`, no focus
 *    trap — same non-modal contract as Float (B1: "not a modal, by
 *    construction"). Confirmed no `Dialog`/`AlertDialog` wrapper here.
 *  - Fullscreen: `role="dialog"` `aria-modal="true"`, WITH a real focus
 *    trap (`useFocusTrap`) — the only mode where trapping is correct,
 *    since nothing else is visibly interactive at that point.
 *  - Escape closes Fullscreen → Expanded. Escape does nothing in Expanded
 *    mode (Expanded has no modal semantics to escape from, same reasoning
 *    as Float never closing on Escape).
 *  - Reduced motion: `useMotionPrefs()` (`lib/animations.ts`) — the exact
 *    hook the architecture doc's B9 cites as already used by
 *    `conversation-sidebar.tsx`/`gravitre-chat-avatar.tsx`. Not reinvented.
 *
 * Portal-rendered to `document.body`, same reasoning as
 * `GravitreFloatingWorkspace`.
 */

import { useEffect, useRef, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { motion } from "framer-motion"
import {
  NucleoChat,
  NucleoClose,
  NucleoCollapse,
  NucleoFullscreen,
  NucleoMinimize,
  NucleoPanelToggle,
} from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { useMotionPrefs } from "@/lib/animations"
import { useFocusTrap } from "@/hooks/use-focus-trap"
import {
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"

export type GravitreAIWorkspaceShellMode = "expanded" | "fullscreen"

export interface GravitreAIWorkspaceShellProps {
  mode: GravitreAIWorkspaceShellMode
  presence: GravitreHelperPresence
  leftPanel: ReactNode
  rightPanel: ReactNode
  leftCollapsed: boolean
  onToggleLeft: () => void
  rightCollapsed: boolean
  onToggleRight: () => void
  /** Collapses back down to the Float window (still open, smaller). */
  onMinimizeToFloat: () => void
  /** Enters Fullscreen. Only meaningful/rendered when `mode === "expanded"`. */
  onEnterFullscreen: () => void
  /** Exits Fullscreen back to Expanded. Also fired by Escape. Only
   * meaningful/rendered when `mode === "fullscreen"`. */
  onExitFullscreen: () => void
  /** Fully closes the floating workspace back down to the Helper bubble. */
  onClose: () => void
  children: ReactNode
}

export function GravitreAIWorkspaceShell({
  mode,
  presence,
  leftPanel,
  rightPanel,
  leftCollapsed,
  onToggleLeft,
  rightCollapsed,
  onToggleRight,
  onMinimizeToFloat,
  onEnterFullscreen,
  onExitFullscreen,
  onClose,
  children,
}: GravitreAIWorkspaceShellProps) {
  const isFullscreen = mode === "fullscreen"
  const containerRef = useRef<HTMLDivElement | null>(null)
  const { reduced: reduceMotion } = useMotionPrefs()

  useFocusTrap(containerRef, isFullscreen)

  useEffect(() => {
    if (!isFullscreen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return
      // Escape must NOT close Float (no modal semantics there) — this
      // listener only exists while mode === "fullscreen", so it structurally
      // cannot fire for Float. It also does nothing in Expanded mode itself
      // (Expanded is non-modal, same as Float).
      event.preventDefault()
      onExitFullscreen()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [isFullscreen, onExitFullscreen])

  if (typeof document === "undefined") return null

  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]

  return createPortal(
    <motion.div
      ref={containerRef}
      tabIndex={-1}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.98 }}
      transition={{ duration: reduceMotion ? 0.01 : 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "pointer-events-auto fixed z-[85] flex flex-col overflow-hidden border border-divide bg-[color:var(--g-surface-1)] shadow-2xl focus:outline-none",
        isFullscreen
          ? "inset-0 rounded-none"
          : "inset-6 rounded-[var(--g-radius-panel)] sm:inset-10 md:inset-x-16 md:inset-y-10",
      )}
      data-gravitre-ai-shell=""
      data-gravitre-ai-shell-mode={mode}
      role={isFullscreen ? "dialog" : "region"}
      aria-modal={isFullscreen ? true : undefined}
      aria-label="Gravitre AI workspace"
    >
      <div className="flex shrink-0 items-center justify-between border-b border-divide px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
            <NucleoChat className="h-3.5 w-3.5" />
          </span>
          <p className="truncate text-xs font-semibold text-[color:var(--g-text-primary)]">Gravitre AI workspace</p>
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
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label={leftCollapsed ? "Show conversation history" : "Hide conversation history"}
            aria-pressed={!leftCollapsed}
            onClick={onToggleLeft}
          >
            <NucleoPanelToggle className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label={rightCollapsed ? "Show context panel" : "Hide context panel"}
            aria-pressed={!rightCollapsed}
            onClick={onToggleRight}
          >
            <NucleoPanelToggle className="h-3.5 w-3.5 scale-x-[-1]" />
          </Button>
          {!isFullscreen ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label="Fullscreen"
              onClick={onEnterFullscreen}
            >
              <NucleoFullscreen className="h-3.5 w-3.5" />
            </Button>
          ) : (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label="Exit fullscreen"
              onClick={onExitFullscreen}
            >
              <NucleoCollapse className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Collapse to floating window"
            onClick={onMinimizeToFloat}
          >
            <NucleoMinimize className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label="Close to helper"
            onClick={onClose}
          >
            <NucleoClose className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/*
          GravitreAILeftPanel (= ConversationSidebar reused as-is, per B2)
          manages its OWN collapsed width via its `isOpen` prop (the caller
          — ai-workspace-shell-bridge.tsx — wires `isOpen={!leftCollapsed}`)
          — it already animates width/opacity/border on that prop, so this
          shell deliberately does NOT wrap it in a second
          mount/unmount-driven collapse container; that would just replace
          ConversationSidebar's own transition with an abrupt unmount.
        */}
        {leftPanel}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">{children}</div>
        {/*
          GravitreAIRightPanel is new (Phase 3) and has no pre-existing
          collapse contract to preserve, so a simple mount/unmount collapse
          is the right amount of engineering here.
        */}
        {!rightCollapsed ? (
          <div className="w-72 shrink-0 overflow-hidden border-l border-divide">{rightPanel}</div>
        ) : null}
      </div>
    </motion.div>,
    document.body,
  )
}
