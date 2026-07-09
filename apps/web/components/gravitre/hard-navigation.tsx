"use client"

import { useEffect } from "react"
import { clearStalePointerLocks } from "./pointer-events-guard"

/**
 * HardNavigation — app-shell-wide workaround for broken soft navigation.
 *
 * Production audit (2026-07-09) confirmed that App Router soft navigation is a
 * silent no-op inside the authenticated shell: `next/link` calls
 * `preventDefault()` on click, then its internal `router.push` never changes
 * the URL, issues no RSC fetch, and throws no error — so nav links appear dead
 * app-wide. Marketing (outside AppShell) is unaffected. Native anchors and
 * `window.location.assign` navigate correctly.
 *
 * Rather than rewrite ~130 files that import `next/link`, we intercept clicks
 * once, in the capture phase, before `next/link`'s delegated (bubble-phase)
 * React handler runs. Calling `preventDefault()` here makes `next/link` bail
 * (see next/dist/client/app-dir/link.js: `if (e.defaultPrevented) return`),
 * and we perform a full navigation instead.
 *
 * This is a deliberate stop-gap so users can navigate today. Remove it once the
 * underlying soft-navigation failure is root-caused and fixed. Guarded so it
 * only ever affects genuine in-app, same-origin, left-click navigations.
 */
export function HardNavigation() {
  useEffect(() => {
    function onClick(event: MouseEvent) {
      // Respect anything already handled, and non-primary / modified clicks
      // (new tab, download, etc.) so default browser behavior is preserved.
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return
      }

      const target = event.target as Element | null
      const anchor = target?.closest?.("a")
      if (!anchor) return

      // Explicit opt-out for the rare link that must keep default behavior.
      if (anchor.dataset.hardNav === "false") return

      const href = anchor.getAttribute("href")
      if (!href) return

      // Skip download links and anything not targeting the current tab.
      if (anchor.hasAttribute("download")) return
      const anchorTarget = anchor.getAttribute("target")
      if (anchorTarget && anchorTarget !== "_self") return

      // Resolve against the current location to classify the destination.
      let url: URL
      try {
        url = new URL(href, window.location.href)
      } catch {
        return
      }

      // Only handle same-origin http(s) navigations. Let the browser handle
      // external links, mailto:, tel:, blob:, etc.
      if (url.origin !== window.location.origin) return
      if (url.protocol !== "http:" && url.protocol !== "https:") return

      // Same-page click (identical path + search): never trigger a full
      // reload. This covers in-page hash scrolls as well as `href="#"`
      // placeholder links, letting the browser handle them natively.
      const samePage = url.pathname === window.location.pathname && url.search === window.location.search
      if (samePage) return

      // This is a genuine in-app navigation. Preempt next/link's (no-op) soft
      // navigation and perform a reliable full navigation instead.
      clearStalePointerLocks()
      event.preventDefault()
      window.location.assign(url.href)
    }

    // Capture phase so we run before next/link's bubble-phase React handler.
    document.addEventListener("click", onClick, true)
    return () => document.removeEventListener("click", onClick, true)
  }, [])

  return null
}
