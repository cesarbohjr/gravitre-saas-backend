"use client"

/**
 * GravitreAIMobileSheet — Phase 4 of the "Gravitre AI Agent Workspace"
 * redesign. The mobile touch-native shell, built on `vaul` (confirmed
 * already an installed dependency — `apps/web/package.json` — and, before
 * this file, used nowhere in the app; verified via a fresh repo-wide grep
 * immediately before writing this file).
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B7 / Part C6 phase row 4: "GravitreAIMobileSheet via vaul ... Reuses
 * the SAME GravitreAIConversation core; only the outer shell swaps." This
 * component owns ONLY window chrome (drag handle, header, snap-point
 * mapping) — exactly like `GravitreFloatingWorkspace` (Phase 2) and
 * `GravitreAIWorkspaceShell` (Phase 3), which it mirrors structurally. It
 * has no opinion about what conversation is inside it; see
 * `apps/web/app/ai/_components/ai-mobile-sheet-bridge.tsx` for the only
 * current caller, which supplies the real, live `/ai` conversation.
 *
 * Snap points (`vaul`'s native mechanism, NOT custom touch handling — per
 * this phase's own instruction: "do not build custom touch handling when
 * vaul already provides this"):
 *   float      → 0.55 of viewport height (BottomSheet)
 *   expanded   → 0.92 of viewport height (ExpandedSheet)
 *   fullscreen → 1    (full viewport)
 * `handleOnly` is set on `Drawer.Root` so only the grabber bar (not the
 * whole sheet body) starts a drag — the composer/transcript below need
 * normal touch-scroll, not accidental sheet-drag, matching the desktop
 * shells' "drag only starts from the header region" rule (B5/item 22).
 *
 * Modal/backdrop contract (B1/B9, carried over from desktop):
 *   - float / expanded: `modal={false}` (no backdrop, underlying page
 *     stays fully interactive — matches Float/Expanded's "not a modal, by
 *     construction"), no `Drawer.Overlay` rendered.
 *   - fullscreen: `modal={true}` WITH `Drawer.Overlay` — the only state
 *     where nothing else is visibly interactive, matching desktop
 *     Fullscreen's real `role="dialog" aria-modal="true"` contract.
 *
 * ⚠️ Disclosed, honest a11y limitation of using `vaul` (built on Radix
 * `Dialog`): Radix's `Dialog.Content` always renders `role="dialog"`
 * regardless of the `modal` prop — `modal` only changes focus-trap/
 * pointer-blocking behavior, not the role attribute. Desktop's Float/
 * Expanded (Phase 2/3, custom `motion.div` chrome, NOT Radix) deliberately
 * use `role="region"` at those same conceptual states (B9: "explicitly
 * NOT role=dialog"). On mobile, using the architecture doc's own mandated
 * library (`vaul`) means Float/Expanded-equivalent snap points still
 * expose `role="dialog"` to assistive tech — a small, real deviation from
 * desktop parity, accepted here because (a) the doc explicitly mandates
 * `vaul`, (b) mobile bottom sheets are conventionally dialog-pattern
 * surfaces on both iOS and Android regardless of "peek" height, so this
 * is closer to platform convention than a regression, and (c)
 * `aria-modal` still only reads `"true"` at the real Fullscreen snap
 * point, which is the accessibility-relevant distinction that actually
 * matters (can the user still reach the rest of the page). Recorded
 * honestly in the Phase 4 delivery report, not silently absorbed.
 */

import { useCallback, useRef, type ReactNode } from "react"
import { Drawer } from "vaul"
import { NucleoChat } from "@/components/icons/nucleo/semantic"
import { ChatWindowControls } from "@/components/gravitre/chat-window-controls"
import { cn } from "@/lib/utils"
import { useFocusTrap } from "@/hooks/use-focus-trap"
import {
  GRAVITRE_HELPER_PRESENCE_COPY,
  GRAVITRE_HELPER_PRESENCE_DOT,
  type GravitreHelperPresence,
} from "@/lib/gravitre-ai-presence"

export type GravitreAIMobileSheetMode = "float" | "expanded" | "fullscreen"

/** Fractions of viewport height per mode — see file header. */
export const GRAVITRE_MOBILE_SHEET_SNAP_POINTS: Record<GravitreAIMobileSheetMode, number> = {
  float: 0.55,
  expanded: 0.92,
  fullscreen: 1,
}

const SNAP_POINT_LIST = [
  GRAVITRE_MOBILE_SHEET_SNAP_POINTS.float,
  GRAVITRE_MOBILE_SHEET_SNAP_POINTS.expanded,
  GRAVITRE_MOBILE_SHEET_SNAP_POINTS.fullscreen,
]

function modeForSnapPoint(snapPoint: number | string | null): GravitreAIMobileSheetMode {
  const numeric = typeof snapPoint === "string" ? Number.parseFloat(snapPoint) : snapPoint
  if (numeric === null || numeric === undefined || Number.isNaN(numeric)) return "float"
  if (numeric >= GRAVITRE_MOBILE_SHEET_SNAP_POINTS.fullscreen) return "fullscreen"
  if (numeric >= GRAVITRE_MOBILE_SHEET_SNAP_POINTS.expanded) return "expanded"
  return "float"
}

export interface GravitreAIMobileSheetProps {
  mode: GravitreAIMobileSheetMode
  presence: GravitreHelperPresence
  /** Fired when the user drags to a different snap point (not only via the
   * header buttons) — keeps `presentationMode` in sync with the gesture. */
  onModeChange: (mode: GravitreAIMobileSheetMode) => void
  /** Dismisses entirely, back to the Helper bubble — fired by the
   * "Minimize to helper" button or by dragging below the smallest snap
   * point (`vaul`'s own `dismissible` gesture handling). */
  onClose: () => void
  children: ReactNode
}

export function GravitreAIMobileSheet({
  mode,
  presence,
  onModeChange,
  onClose,
  children,
}: GravitreAIMobileSheetProps) {
  const contentRef = useRef<HTMLDivElement | null>(null)
  const isFullscreen = mode === "fullscreen"
  const copy = GRAVITRE_HELPER_PRESENCE_COPY[presence]

  useFocusTrap(contentRef, isFullscreen)

  const handleSnapPointChange = useCallback(
    (snapPoint: number | string | null) => {
      const next = modeForSnapPoint(snapPoint)
      if (next !== mode) onModeChange(next)
    },
    [mode, onModeChange],
  )

  const cycleUp = useCallback(() => {
    if (mode === "float") onModeChange("expanded")
    else if (mode === "expanded") onModeChange("fullscreen")
  }, [mode, onModeChange])

  // cycleDown is gone: the controls now name their destination directly rather
  // than sharing one button whose meaning changed with the mode.

  return (
    <Drawer.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      modal={isFullscreen}
      dismissible
      handleOnly
      snapPoints={SNAP_POINT_LIST}
      activeSnapPoint={GRAVITRE_MOBILE_SHEET_SNAP_POINTS[mode]}
      setActiveSnapPoint={handleSnapPointChange}
    >
      <Drawer.Portal>
        {isFullscreen ? (
          <Drawer.Overlay className="fixed inset-0 z-[84] bg-black/40" data-gravitre-mobile-sheet-overlay="" />
        ) : null}
        <Drawer.Content
          ref={contentRef}
          data-gravitre-mobile-sheet=""
          data-gravitre-mobile-sheet-mode={mode}
          onEscapeKeyDown={(event) => {
            // Escape never fully closes the sheet — mirrors desktop's
            // Fullscreen→Expanded contract, and does nothing at
            // float/expanded (no modal semantics to escape from there).
            event.preventDefault()
            if (isFullscreen) onModeChange("expanded")
          }}
          className={cn(
            "fixed inset-x-0 bottom-0 z-[85] flex flex-col overflow-hidden border-t border-divide bg-[color:var(--g-surface-1)] shadow-2xl focus:outline-none",
            isFullscreen ? "inset-0 rounded-none" : "rounded-t-[var(--g-radius-panel)]",
          )}
          aria-label="Gravitre AI"
        >
          <Drawer.Title className="sr-only">Gravitre AI</Drawer.Title>
          <Drawer.Description className="sr-only">
            {`Gravitre AI conversation — ${copy.label.toLowerCase()}.`}
          </Drawer.Description>
          {!isFullscreen ? (
            <Drawer.Handle
              preventCycle
              onClick={cycleUp}
              data-gravitre-mobile-sheet-handle=""
              className="mx-auto mt-2 h-1.5 w-10 shrink-0 rounded-full bg-[color:var(--g-surface-2)]"
              aria-label="Expand Gravitre AI"
            />
          ) : null}
          <div className="flex shrink-0 items-center justify-between border-b border-divide px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
                <NucleoChat className="h-3.5 w-3.5" />
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
            {/*
              Uses the same per-mode manifest as the desktop shells rather than a
              mobile-specific list, so the two cannot drift. Previously one button
              here served two different actions via a conditional aria-label, and
              fullscreen offered no direct route back to the floating window.
            */}
            <ChatWindowControls
              surface={mode}
              handlers={{
                expand: () => onModeChange("expanded"),
                fullscreen: () => onModeChange("fullscreen"),
                exitFullscreen: () => onModeChange("expanded"),
                collapseToFloat: () => onModeChange("float"),
                minimizeToHelper: onClose,
              }}
            />
          </div>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}
