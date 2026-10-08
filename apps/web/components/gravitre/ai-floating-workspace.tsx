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
 * `apps/web/app/(app)/ai/_components/ai-workspace-float-bridge.tsx`, the only
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
 *
 * Phase 4 addendum (C1 icon-gap closure): the header's "Expand"/"Minimize
 * to helper" controls now use `NucleoExpand`/`NucleoMinimize` (Nucleo-STYLE
 * constructions, see `components/icons/nucleo/semantic.tsx`'s file header)
 * instead of Lucide `Expand`/`Minimize2`, matching `ai-workspace-shell.tsx`'s
 * equivalent controls. `GripVertical` (drag handle + resize handle) is
 * unchanged — the one already-approved Lucide exception.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type PointerEvent, type PropsWithChildren, type ReactNode } from "react"
import { createPortal } from "react-dom"
import { motion, useDragControls, useMotionValue, useReducedMotion } from "framer-motion"
// GripVertical is the ONE approved Lucide exception for the drag-handle/
// resize-handle affordance (Phase 3) — do not replace it (see the
// architecture doc's C1 audit and this phase's own instructions).
import { GripVertical } from "lucide-react"
import { NucleoChat } from "@/components/icons/nucleo/semantic"
import { ChatWindowControls } from "@/components/gravitre/chat-window-controls"
import { cn } from "@/lib/utils"
import {
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"
import { useWindowResize, type WindowSize } from "@/hooks/use-window-resize"
import { WINDOW_CHROME, TYPE, MOTION } from "@/lib/design-system"
import { GRAVITRE_AI_WORKSPACE_LAYOUT_ID } from "@/lib/gravitre-ai-presentation"
import {
  clampFloatSize,
  clampFloatTranslate,
  GRAVITRE_FLOAT_DEFAULT_SIZE,
  GRAVITRE_FLOAT_MAX_SIZE,
  GRAVITRE_FLOAT_MIN_SIZE,
  readStoredFloatGeometry,
  writeStoredFloatGeometry,
} from "@/lib/ai-float-geometry"

/** Re-export size constants for tests / callers (canonical: lib/ai-float-geometry). */
export { GRAVITRE_FLOAT_DEFAULT_SIZE, GRAVITRE_FLOAT_MIN_SIZE, GRAVITRE_FLOAT_MAX_SIZE }

export type GravitreFloatingWorkspaceProps = PropsWithChildren<{
  presence: GravitreHelperPresence
  /** Returns the workspace to Helper presentation mode. */
  onClose: () => void
  /** Transitions to Expanded mode (GravitreAIWorkspaceShell). Omitted →
   * no Expand button renders (keeps this shell usable standalone in tests). */
  onExpand?: () => void
  /** Transitions straight to Fullscreen. Previously unreachable from here, so
   * fullscreen took two steps (expand, then fullscreen) for no reason. */
  onEnterFullscreen?: () => void
  /** Docks the window to the right edge. Omitted → no Dock control. */
  onDock?: () => void
  /** Returns a docked window to a floating window. */
  onUndock?: () => void
  /**
   * `window` is the draggable float; `docked` pins the same element to the right
   * edge at full height. Same component instance either way, so switching never
   * remounts the conversation inside it.
   */
  placement?: "window" | "docked"
  /** Compact is the small default window; floating opens larger. */
  variant?: "compact" | "floating"
  titleAccessory?: ReactNode
}>

/** Default size for the larger `floating` variant when no geometry is stored. */
export const GRAVITRE_FLOATING_VARIANT_DEFAULT_SIZE: WindowSize = { width: 640, height: 640 }

/** Body attribute that reserves page space for the dock on md+ (see globals.css). */
export const GRAVITRE_WM_DOCKED_BODY_ATTR = "data-gravitre-wm-docked"

export function GravitreFloatingWorkspace({
  presence,
  onClose,
  onExpand,
  onEnterFullscreen,
  onDock,
  onUndock,
  placement = "window",
  variant = "compact",
  titleAccessory,
  children,
}: GravitreFloatingWorkspaceProps) {
  const docked = placement === "docked"
  const dragControls = useDragControls()
  const reduceMotion = useReducedMotion()
  const [viewport, setViewport] = useState<{ width: number; height: number } | null>(null)
  const [size, setSize] = useState<WindowSize>(GRAVITRE_FLOAT_DEFAULT_SIZE)
  const dragX = useMotionValue(0)
  const dragY = useMotionValue(0)
  const [geometryHydrated, setGeometryHydrated] = useState(false)

  const [keyboardInset, setKeyboardInset] = useState(0)

  useEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    update()
    window.addEventListener("resize", update)
    const vv = window.visualViewport
    const syncKeyboard = () => {
      if (!vv) {
        setKeyboardInset(0)
        return
      }
      setKeyboardInset(Math.max(0, window.innerHeight - vv.height - vv.offsetTop))
    }
    syncKeyboard()
    vv?.addEventListener("resize", syncKeyboard)
    vv?.addEventListener("scroll", syncKeyboard)
    return () => {
      window.removeEventListener("resize", update)
      vv?.removeEventListener("resize", syncKeyboard)
      vv?.removeEventListener("scroll", syncKeyboard)
    }
  }, [])

  // Phase 5 — restore session geometry once viewport is known; clamp if stale.
  useEffect(() => {
    if (!viewport || geometryHydrated) return
    const stored = readStoredFloatGeometry(viewport)
    if (stored) {
      setSize(clampFloatSize({ width: stored.width, height: stored.height }, viewport))
      dragX.set(stored.x)
      dragY.set(stored.y)
    } else if (variant === "floating") {
      setSize(clampFloatSize(GRAVITRE_FLOATING_VARIANT_DEFAULT_SIZE, viewport))
    }
    setGeometryHydrated(true)
  }, [viewport, geometryHydrated, dragX, dragY, variant])

  // Docked reserves page width so the page stays usable beside the dock.
  useEffect(() => {
    if (!docked) return
    document.body.setAttribute(GRAVITRE_WM_DOCKED_BODY_ATTR, "")
    return () => document.body.removeAttribute(GRAVITRE_WM_DOCKED_BODY_ATTR)
  }, [docked])

  const persistGeometry = useCallback(
    (nextSize: WindowSize) => {
      if (!viewport) return
      const pos = clampFloatTranslate({ x: dragX.get(), y: dragY.get() }, viewport)
      dragX.set(pos.x)
      dragY.set(pos.y)
      writeStoredFloatGeometry({
        width: nextSize.width,
        height: nextSize.height,
        x: pos.x,
        y: pos.y,
      })
    },
    [dragX, dragY, viewport],
  )

  const maxSize = useMemo<WindowSize>(() => {
    if (!viewport) return GRAVITRE_FLOAT_MAX_SIZE
    return clampFloatSize(GRAVITRE_FLOAT_MAX_SIZE, {
      width: viewport.width,
      height: Math.max(320, viewport.height - keyboardInset),
    })
  }, [keyboardInset, viewport])

  const { onPointerDown: onResizePointerDown, onKeyDown: onResizeKeyDown } = useWindowResize({
    size,
    min: GRAVITRE_FLOAT_MIN_SIZE,
    max: maxSize,
    onResize: (next) => {
      setSize(next)
      persistGeometry(next)
    },
  })

  // The window is anchored by CSS (bottom + a left offset that clears the nav
  // rail, matching the launcher). Drag constraints are translations relative to
  // that untransformed origin, so they have to be derived from it — a fixed
  // {top: 8, left: 8} only works for an element anchored at the top-left corner.
  const frameRef = useRef<HTMLDivElement | null>(null)
  const [originLeft, setOriginLeft] = useState(16)
  const measureOrigin = useCallback(() => {
    const el = frameRef.current
    if (!el) return
    const left = Number.parseFloat(getComputedStyle(el).left)
    if (Number.isFinite(left)) setOriginLeft(left)
  }, [])
  useLayoutEffect(() => {
    if (!docked) measureOrigin()
  }, [docked, measureOrigin, viewport])

  const onHeaderPointerDown = useCallback(
    (event: PointerEvent<HTMLDivElement>) => {
      // Never start a drag from an interactive control inside the header —
      // architecture doc item 22: drag must not swallow button clicks.
      if (docked) return
      const target = event.target as HTMLElement
      if (target.closest("button,a,input,textarea")) return
      measureOrigin()
      dragControls.start(event)
    },
    [dragControls, docked, measureOrigin],
  )

  if (typeof document === "undefined" || !viewport) return null

  const edge = 8
  const bottomOffset = 16 + keyboardInset
  const originTop = viewport.height - bottomOffset - size.height
  // When the origin already clears the nav rail (md+), never let a drag carry
  // the window back over it — the rail is essential navigation.
  const minX = originLeft > 24 ? 0 : edge - originLeft
  const dragBounds = {
    left: minX,
    right: Math.max(minX, viewport.width - edge - originLeft - size.width),
    top: Math.min(0, edge - originTop),
    bottom: 0,
  }

  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]

  return createPortal(
    <motion.div
      ref={frameRef}
      layoutId={reduceMotion ? undefined : GRAVITRE_AI_WORKSPACE_LAYOUT_ID}
      drag={!docked}
      dragListener={false}
      dragControls={dragControls}
      dragMomentum={false}
      dragElastic={0}
      style={
        docked
          ? { x: 0, y: 0, width: "var(--g-wm-dock-width)", height: "100dvh" }
          : {
              x: dragX,
              y: dragY,
              width: size.width,
              height: size.height,
              bottom: bottomOffset,
            }
      }
      dragConstraints={dragBounds}
      onDragEnd={() => persistGeometry(size)}
      initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
      transition={{ duration: reduceMotion ? 0 : MOTION.major, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "pointer-events-auto fixed z-[85] flex flex-col overflow-hidden",
        WINDOW_CHROME.frame,
        docked
          ? "inset-y-0 right-0 rounded-none border-y-0 border-r-0"
          : "left-4 max-h-[min(100dvh-2rem,760px)] md:left-[calc(var(--np-sidebar-rail)+12px)] md:[:root:has([data-nav-expanded=true])_&]:left-[calc(var(--np-sidebar)+12px)]",
      )}
      data-gravitre-float-workspace=""
      data-gravitre-wm-placement={docked ? "docked" : "window"}
      data-gravitre-wm-variant={docked ? undefined : variant}
      data-gravitre-workspace-layout-id={reduceMotion ? "reduced-motion" : GRAVITRE_AI_WORKSPACE_LAYOUT_ID}
      role="region"
      aria-label={docked ? "Gravitre AI, docked" : "Gravitre AI"}
    >
      <div
        onPointerDown={onHeaderPointerDown}
        data-window-drag-handle={docked ? undefined : ""}
        className={cn(
          WINDOW_CHROME.header,
          "justify-between gap-2",
          !docked && "cursor-grab select-none active:cursor-grabbing",
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          {docked ? null : <GripVertical className="h-3.5 w-3.5 text-[color:var(--g-text-muted)]" aria-hidden />}
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
            <NucleoChat className="h-3.5 w-3.5" />
          </span>
          <div className="min-w-0">
            <p className={cn(TYPE.cardTitle, "truncate")}>Gravitre AI</p>
            {titleAccessory}
          </div>
          <span
            className={cn(
              "ml-1 hidden shrink-0 items-center gap-1 rounded-full bg-[color:var(--g-surface-2)] px-1.5 py-0.5 text-[10px] font-medium sm:flex",
              copy.tone,
            )}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", GRAVITRE_HELPER_PRESENCE_DOT[presence])} aria-hidden />
            {copy.label}
          </span>
        </div>
        <ChatWindowControls
          surface={docked ? "docked" : "float"}
          handlers={{
            expand: onExpand,
            fullscreen: onEnterFullscreen,
            minimizeToHelper: onClose,
            dock: onDock,
            undock: onUndock,
          }}
        />
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
      {docked ? null : (
        <>
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
        </>
      )}
    </motion.div>,
    document.body,
  )
}
