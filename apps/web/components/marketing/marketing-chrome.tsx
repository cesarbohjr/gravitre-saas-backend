"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { Navbar } from "@/components/marketing/nodus/navbar"
import { Footer } from "@/components/marketing/nodus/footer"
import { DivideX } from "@/components/marketing/nodus/divide"

const AUTH_FOOTER_SLIM_PATHS = new Set(["/login", "/get-started", "/forgot-password"])

/**
 * Marketing chrome — Nodus Agent Template layout (light-first, Gravitre brand).
 * Auth routes use a slim legal footer (gate: auth chrome slim).
 */
export function MarketingChrome({ children }: { children: React.ReactNode }) {
  const { setTheme } = useTheme()
  const pathname = usePathname()
  const slimFooter = AUTH_FOOTER_SLIM_PATHS.has(pathname)

  useEffect(() => {
    const root = document.documentElement
    root.dataset.marketingCanvas = "daylight"
    setTheme("light")
    return () => {
      delete root.dataset.marketingCanvas
      setTheme("light")
    }
  }, [setTheme])

  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-charcoal-900" data-marketing-canvas="daylight">
      <Navbar />
      <DivideX />
      {children}
      <DivideX />
      <Footer variant={slimFooter ? "slim" : "full"} />
    </div>
  )
}
