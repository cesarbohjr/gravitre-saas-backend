"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"

type ViewMode = "admin" | "lite"

type LiteMembership = {
  is_lite: boolean
  is_admin: boolean
  department: { id: string; name: string } | null
}

interface ViewModeContextType {
  mode: ViewMode
  setMode: (mode: ViewMode) => void
  isLite: boolean
  isAdmin: boolean
  liteDepartment: { id: string; name: string } | null
  membershipLoading: boolean
}

const ViewModeContext = createContext<ViewModeContextType | undefined>(undefined)

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { data: membership, isLoading } = useSWR<LiteMembership>(
    user ? "/api/settings/lite-membership" : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )

  const serverLite = Boolean(membership?.is_lite)
  const serverAdmin = membership?.is_admin !== false

  const [manualOverride, setManualOverride] = useState<ViewMode | null>(() => {
    if (typeof window === "undefined") return null
    const stored = window.localStorage.getItem("gravitre-view-mode")
    return stored === "lite" || stored === "admin" ? stored : null
  })

  useEffect(() => {
    if (serverLite) {
      setManualOverride("lite")
      localStorage.setItem("gravitre-view-mode", "lite")
    }
  }, [serverLite])

  const mode: ViewMode = serverLite ? "lite" : manualOverride ?? "admin"

  const setMode = (newMode: ViewMode) => {
    if (serverLite && newMode === "admin" && !serverAdmin) {
      return
    }
    setManualOverride(newMode)
    localStorage.setItem("gravitre-view-mode", newMode)
  }

  return (
    <ViewModeContext.Provider
      value={{
        mode,
        setMode,
        isLite: mode === "lite",
        isAdmin: serverAdmin && mode === "admin",
        liteDepartment: membership?.department ?? null,
        membershipLoading: isLoading,
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

export function useViewModeSafe() {
  const context = useContext(ViewModeContext)
  if (context === undefined) {
    return {
      mode: "admin" as ViewMode,
      setMode: () => {},
      isLite: false,
      isAdmin: true,
      liteDepartment: null,
      membershipLoading: false,
    }
  }
  return context
}
