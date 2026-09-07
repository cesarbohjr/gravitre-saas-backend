"use client"

import { useEffect } from "react"
import { useTheme } from "next-themes"
import { Navbar } from "@/components/marketing/nodus/navbar"
import { Footer } from "@/components/marketing/nodus/footer"
import { DivideX } from "@/components/marketing/nodus/divide"

/**
 * Marketing chrome — Nodus Agent Template layout (light-first, Gravitre brand).
 */
export function MarketingChrome({ children }: { children: React.ReactNode }) {
  const { setTheme } = useTheme()

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
    <div className="min-h-screen bg-white text-charcoal-900" data-marketing-canvas="daylight">
      <Navbar />
      <DivideX />
      {children}
      <DivideX />
      <Footer />
    </div>
  )
}
