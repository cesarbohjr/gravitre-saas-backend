"use client"

/**
 * useFocusTrap — Phase 3 of the "Gravitre AI Agent Workspace" redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B9: "Fullscreen mode: role="dialog" aria-modal="true" WITH a focus
 * trap — the only mode where trapping is actually correct." Float and
 * Expanded must NOT use this hook (`active` should be `false` for them) —
 * see B1/B9: "not a modal, by construction."
 *
 * No focus-trap utility existed anywhere in this codebase before this file
 * (confirmed via repo-wide grep for `focus.?trap`/`trapFocus` prior to
 * writing this). This is a small, dependency-free implementation rather
 * than pulling in a new library, consistent with this program's general
 * preference for minimal new dependencies (see B5's react-rnd rejection).
 */

import { useEffect, useRef, type RefObject } from "react"

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",")

function getFocusable(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
}

/**
 * Traps Tab/Shift+Tab focus cycling within `containerRef` while `active` is
 * true. On activation, focuses the first focusable descendant (falling back
 * to the container itself, which must be focusable — e.g. `tabIndex={-1}`).
 * On deactivation, restores focus to whatever had it before activation.
 */
export function useFocusTrap(containerRef: RefObject<HTMLElement | null>, active: boolean): void {
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!active) return
    const container = containerRef.current
    if (!container) return

    previouslyFocused.current = document.activeElement as HTMLElement | null

    const initial = getFocusable(container)[0] ?? container
    initial.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return
      const items = getFocusable(container)
      if (items.length === 0) {
        event.preventDefault()
        container.focus()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const activeEl = document.activeElement

      if (event.shiftKey) {
        if (activeEl === first || !container.contains(activeEl)) {
          event.preventDefault()
          last.focus()
        }
      } else if (activeEl === last || !container.contains(activeEl)) {
        event.preventDefault()
        first.focus()
      }
    }

    container.addEventListener("keydown", onKeyDown)
    return () => {
      container.removeEventListener("keydown", onKeyDown)
      const toRestore = previouslyFocused.current
      if (toRestore && typeof toRestore.focus === "function") {
        toRestore.focus()
      }
    }
  }, [active, containerRef])
}
