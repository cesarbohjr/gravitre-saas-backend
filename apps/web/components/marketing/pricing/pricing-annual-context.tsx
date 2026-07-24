"use client"

import { createContext, useContext, useState, type ReactNode } from "react"

type PricingAnnualContextValue = {
  isAnnual: boolean
  setIsAnnual: (value: boolean) => void
}

const PricingAnnualContext = createContext<PricingAnnualContextValue | null>(null)

export function PricingAnnualProvider({ children }: { children: ReactNode }) {
  const [isAnnual, setIsAnnual] = useState(false)

  return (
    <PricingAnnualContext.Provider value={{ isAnnual, setIsAnnual }}>
      {children}
    </PricingAnnualContext.Provider>
  )
}

export function usePricingAnnual() {
  const context = useContext(PricingAnnualContext)
  if (!context) {
    throw new Error("usePricingAnnual must be used within PricingAnnualProvider")
  }
  return context
}
