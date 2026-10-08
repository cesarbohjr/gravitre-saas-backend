"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/**
 * Lite home redirects into the shared Home shell (Phase 1).
 * Progressive disclosure is handled by the shared sidebar + seat entitlements —
 * not a separately maintained Lite dashboard.
 */
export default function LiteHomeRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace(APP_ROUTES.home)
  }, [router])
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
      Opening Home…
    </div>
  )
}
