"use client"

/**
 * useGravitreMobileViewport — Phase 4 of the "Gravitre AI Agent Workspace"
 * redesign.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B7: "The existing `md` breakpoint (768px) already governs
 * `MobileBottomNav`, `ConversationSidebar`'s drawer mode, and
 * `LiveActivityRail`'s drawer mode ... reuse it as the desktop↔mobile-sheet
 * cutover rather than inventing a new one."
 *
 * Confirmed by reading `apps/web/app/globals.css` fresh: no
 * `--breakpoint-*`/`screens` override exists, so Tailwind v4's default `md`
 * (`(min-width: 768px)`) is the real, live cutover value — this hook's
 * `(max-width: 767px)` query is its exact complement, not a guess.
 *
 * `matchMedia`-based (not a `resize` listener + `window.innerWidth` poll)
 * so it fires once per actual breakpoint crossing, not once per pixel of
 * resize — and so it degrades safely to `false` (desktop) in any
 * environment without `matchMedia` (SSR, and any test environment that
 * hasn't stubbed it), matching this file's own default state.
 */

import { useEffect, useState } from "react"

const MOBILE_MEDIA_QUERY = "(max-width: 767px)"

export function useGravitreMobileViewport(): boolean {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return

    const mql = window.matchMedia(MOBILE_MEDIA_QUERY)
    setIsMobile(mql.matches)

    const onChange = (event: MediaQueryListEvent) => setIsMobile(event.matches)
    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange)
      return () => mql.removeEventListener("change", onChange)
    }
    // Safari <14 fallback — addListener/removeListener are deprecated but
    // this keeps the hook from silently doing nothing on old engines.
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    mql.addListener(onChange)
    // eslint-disable-next-line @typescript-eslint/no-deprecated
    return () => mql.removeListener(onChange)
  }, [])

  return isMobile
}
