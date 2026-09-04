"use client"

import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { faqs } from "@/lib/pricing-page-data"

export function PricingFaqAccordion() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      {faqs.map((faq, i) => (
        <div
          key={faq.question}
          className="rounded-2xl border border-border bg-card overflow-hidden shadow-sm"
        >
          <button
            type="button"
            onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
            className="w-full flex items-center justify-between p-6 text-left hover:bg-muted/50 transition-colors"
          >
            <span className="font-medium text-foreground pr-4">{faq.question}</span>
            <div
              className={`shrink-0 h-6 w-6 rounded-full bg-muted flex items-center justify-center transition-transform ${
                expandedFaq === i ? "rotate-90" : ""
              }`}
            >
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            </div>
          </button>
          {expandedFaq === i && (
            <div className="px-6 pb-6 text-sm text-muted-foreground leading-relaxed">
              {faq.answer}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
