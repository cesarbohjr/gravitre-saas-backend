"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"

/**
 * Clears stale Radix/react-remove-scroll locks that can survive AppShell
 * remounts (AppShell is still mounted per-page). When body keeps
 * `data-scroll-locked` / `pointer-events: none` with no open dialog/menu,
 * sidebar links show a pointer cursor but clicks do nothing.
 */
function hasOpenOverlay(): boolean {
  if (typeof document === "undefined") return false
  return Boolean(
    document.querySelector(
      [
        '[data-slot="dialog-overlay"][data-state="open"]',
        '[data-slot="dialog-content"][data-state="open"]',
        '[role="dialog"][data-state="open"]',
        '[data-slot="dropdown-menu-content"][data-state="open"]',
        '[data-radix-menu-content][data-state="open"]',
        '[data-radix-popper-content-wrapper] [data-state="open"]',
        '[data-state="open"][data-slot="select-content"]',
        '[data-state="open"][role="listbox"]',
      ].join(", "),
    ),
  )
}

export function clearStalePointerLocks(): boolean {
  if (typeof document === "undefined") return false
  if (hasOpenOverlay()) return false

  let cleared = false
  const { body, documentElement } = document

  if (body.hasAttribute("data-scroll-locked")) {
    body.removeAttribute("data-scroll-locked")
    cleared = true
  }

  // react-remove-scroll may set inline styles on body / html
  for (const el of [body, documentElement]) {
    if (el.style.pointerEvents === "none") {
      el.style.pointerEvents = ""
      cleared = true
    }
    if (el.style.overflow === "hidden" && !hasOpenOverlay()) {
      el.style.removeProperty("overflow")
      cleared = true
    }
    if (el.style.paddingRight) {
      el.style.removeProperty("padding-right")
      cleared = true
    }
    if (el.style.marginRight) {
      el.style.removeProperty("margin-right")
      cleared = true
    }
  }

  // Orphaned full-viewport backdrops left after AnimatePresence + remount races
  document.querySelectorAll(".fixed.inset-0").forEach((node) => {
    const el = node as HTMLElement
    if (el.dataset.gravitreKeepOverlay === "true") return
    const pe = getComputedStyle(el).pointerEvents
    const opacity = Number.parseFloat(getComputedStyle(el).opacity || "1")
    const z = Number.parseInt(getComputedStyle(el).zIndex || "0", 10)
    // Only remove invisible / empty catchers that sit above the sidebar (z>=30)
    // and are not part of an open Radix dialog.
    if (
      pe !== "none" &&
      z >= 30 &&
      opacity < 0.05 &&
      !el.querySelector("[data-state='open']") &&
      el.childElementCount === 0
    ) {
      el.style.pointerEvents = "none"
      cleared = true
    }
  })

  return cleared
}

export function PointerEventsGuard() {
  const pathname = usePathname()

  useEffect(() => {
    clearStalePointerLocks()
    // Allow exit animations / remount races to settle, then clear again.
    const t1 = window.setTimeout(clearStalePointerLocks, 50)
    const t2 = window.setTimeout(clearStalePointerLocks, 300)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
    }
  }, [pathname])

  useEffect(() => {
    const onPointerDown = () => {
      clearStalePointerLocks()
    }
    // Capture phase so locks are cleared before the click target is resolved.
    document.addEventListener("pointerdown", onPointerDown, true)

    const observer = new MutationObserver(() => {
      window.requestAnimationFrame(() => clearStalePointerLocks())
    })
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-scroll-locked", "style", "class"],
    })

    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true)
      observer.disconnect()
    }
  }, [])

  return null
}
