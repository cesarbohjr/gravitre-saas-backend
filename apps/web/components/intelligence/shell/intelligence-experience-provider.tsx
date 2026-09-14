"use client"

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react"

type IntelligenceExperienceContextValue = {
  inspectorPinned: boolean
  setInspectorPinned: (pinned: boolean) => void
  toggleInspectorPinned: () => void
}

const IntelligenceExperienceContext = createContext<IntelligenceExperienceContextValue | null>(
  null,
)

export function IntelligenceExperienceProvider({ children }: { children: ReactNode }) {
  const [inspectorPinned, setInspectorPinned] = useState(false)
  const toggleInspectorPinned = useCallback(
    () => setInspectorPinned((prev) => !prev),
    [],
  )

  const value = useMemo(
    () => ({
      inspectorPinned,
      setInspectorPinned,
      toggleInspectorPinned,
    }),
    [inspectorPinned, toggleInspectorPinned],
  )

  return (
    <IntelligenceExperienceContext.Provider value={value}>
      {children}
    </IntelligenceExperienceContext.Provider>
  )
}

export function useIntelligenceExperience() {
  const ctx = useContext(IntelligenceExperienceContext)
  if (!ctx) {
    throw new Error("useIntelligenceExperience must be used within IntelligenceExperienceProvider")
  }
  return ctx
}

/** Safe optional access for routes not yet wrapped by the provider. */
export function useIntelligenceExperienceOptional() {
  return useContext(IntelligenceExperienceContext)
}
