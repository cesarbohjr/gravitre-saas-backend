"use client"

import { Star } from "lucide-react"
import { tiers } from "@/lib/pricing-page-data"
import { usePricingAnnual } from "./pricing-annual-context"

export function PricingComparisonPrices() {
  const { isAnnual } = usePricingAnnual()

  return (
    <>
      {tiers.map((tier) => {
        const displayPrice = isAnnual ? tier.price.annual : tier.price.monthly
        const planMeta =
          tier.name === "Control"
            ? { desc: "Most popular", highlighted: true as const }
            : tier.name === "Node"
              ? { desc: "For individuals", highlighted: false as const }
              : { desc: "For teams", highlighted: false as const }

        return (
          <div
            key={tier.name}
            className={`p-6 text-center ${planMeta.highlighted ? "bg-gradient-to-b from-amber-50 to-amber-50/30 relative pt-10" : "bg-white"}`}
          >
            {planMeta.highlighted && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-1 text-xs font-semibold text-white shadow-sm">
                  <Star className="h-3 w-3 fill-white text-white" />
                  Popular
                </span>
              </div>
            )}
            <h3 className="font-semibold text-zinc-900 text-lg">{tier.name}</h3>
            <div className="mt-1">
              <span className="text-2xl font-bold text-zinc-900">${displayPrice}</span>
              <span className="text-sm text-zinc-500">/mo</span>
            </div>
            <p className="mt-1 text-xs text-zinc-500">{planMeta.desc}</p>
          </div>
        )
      })}
    </>
  )
}
