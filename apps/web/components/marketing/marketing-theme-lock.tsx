"use client"

import { useEffect } from "react"
import { useTheme } from "next-themes"

/** Keeps marketing routes on light / daylight canvas tokens. */
export function MarketingThemeLock() {
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

  return null
}
