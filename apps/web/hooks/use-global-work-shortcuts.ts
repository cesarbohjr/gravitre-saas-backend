"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  dispatchToggleNav,
  dispatchWorkShortcut,
  isEditableTarget,
} from "@/lib/work-page-shortcuts"

export function useGlobalWorkShortcuts() {
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey
      if (!mod || isEditableTarget(event.target)) return

      const key = event.key.toLowerCase()

      // ⌘B / Ctrl+B — collapse or expand the sidebar rail (desktop densify).
      if (key === "b") {
        event.preventDefault()
        dispatchToggleNav()
        return
      }

      if (key === "n") {
        event.preventDefault()

        if (pathname.startsWith("/agents")) {
          router.push("/agents/new")
          return
        }
        if (pathname.startsWith("/workflows")) {
          router.push("/workflows/new/builder")
          return
        }
        if (
          pathname.startsWith("/assignments") ||
          pathname.startsWith("/ai") ||
          pathname.startsWith(APP_ROUTES.gravitreAi)
        ) {
          dispatchWorkShortcut("new")
        }
        return
      }

      if (event.key === "/") {
        event.preventDefault()
        dispatchWorkShortcut("focus-search")
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [pathname, router])
}
