"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

type ViewMode = "admin" | "lite"

interface ViewModeContextType {
  mode: ViewMode
  setMode: (mode: ViewMode) => void
  isLite: boolean
  isAdmin: boolean
}

const ViewModeContext = createContext<ViewModeContextType | undefined>(undefined)

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ViewMode>("admin")

  useEffect(() => {
    const stored = localStorage.getItem("gravitre-view-mode") as ViewMode | null
    if (stored === "admin" || stored === "lite") {
      setModeState(stored)
    }
  }, [])

  const setMode = (newMode: ViewMode) => {
    setModeState(newMode)
    localStorage.setItem("gravitre-view-mode", newMode)
  }

  return (
    <ViewModeContext.Provider
      value={{
        mode,
        setMode,
        isLite: mode === "lite",
        isAdmin: mode === "admin",
      }}
    >
      {children}
    </ViewModeContext.Provider>
  )
}

export function useViewMode() {
  const context = useContext(ViewModeContext)
  if (context === undefined) {
    throw new Error("useViewMode must be used within a ViewModeProvider")
  }
  return context
}

// Safe version that returns default values when outside provider (e.g., on marketing pages)
export function useViewModeSafe() {
  const context = useContext(ViewModeContext)
  if (context === undefined) {
    return {
      mode: "admin" as const,
      setMode: () => {},
      isLite: false,
      isAdmin: false, // Default to false when outside provider (hides admin-only features on marketing pages)
    }
  }
  return context
}
