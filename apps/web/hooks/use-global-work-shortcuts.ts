"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  dispatchWorkShortcut,
  isEditableTarget,
} from "@/lib/work-page-shortcuts"

export function useGlobalWorkShortcuts() {
  const pathname = usePathname()
  const router = useRouter()

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey

      if (mod && event.key.toLowerCase() === "n") {
        if (isEditableTarget(event.target)) return
        event.preventDefault()

        if (pathname.startsWith("/agents")) {
          router.push("/agents/new")
          return
        }
        if (
          pathname.startsWith("/assignments") ||
          pathname.startsWith("/assistant") ||
          pathname.startsWith(APP_ROUTES.commandCenter)
        ) {
          dispatchWorkShortcut("new")
        }
        return
      }

      if (mod && event.key === "/") {
        if (isEditableTarget(event.target)) return
        event.preventDefault()
        dispatchWorkShortcut("focus-search")
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [pathname, router])
}
