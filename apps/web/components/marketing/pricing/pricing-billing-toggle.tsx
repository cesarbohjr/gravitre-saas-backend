"use client"

import { usePricingAnnual } from "./pricing-annual-context"

export function PricingBillingToggle() {
  const { isAnnual, setIsAnnual } = usePricingAnnual()

  return (
    <>
      <div className="mt-8 sm:mt-10 inline-flex items-center gap-2 sm:gap-4 rounded-full border border-border bg-card/80 backdrop-blur-sm p-1 sm:p-1.5 shadow-lg shadow-zinc-200/50">
        <button
          type="button"
          onClick={() => setIsAnnual(false)}
          className={`relative rounded-full px-4 sm:px-6 py-2 text-xs sm:text-sm font-medium transition-all ${
            !isAnnual
              ? "bg-foreground text-white shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Monthly
        </button>
        <button
          type="button"
          onClick={() => setIsAnnual(true)}
          className={`relative rounded-full px-4 sm:px-6 py-2 text-xs sm:text-sm font-medium transition-all flex items-center gap-1.5 sm:gap-2 ${
            isAnnual
              ? "bg-foreground text-white shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Annual
          <span
            className={`text-[10px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded-full ${
              isAnnual ? "bg-primary/100 text-white" : "bg-primary/15 text-primary"
            }`}
          >
            2 months free
          </span>
        </button>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        {isAnnual
          ? "Annual billing — per-month equivalent shown (billed yearly)"
          : "Prices in USD · billed monthly"}
      </p>
    </>
  )
}
