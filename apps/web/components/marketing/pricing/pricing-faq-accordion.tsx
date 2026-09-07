"use client"

import { useState } from "react"
import { faqs } from "@/lib/pricing-page-data"
import { cn } from "@/lib/utils"

/** Nodus-style FAQ accordion for `/pricing`. */
export function PricingFaqAccordion() {
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)

  return (
    <div className="border-divide divide-divide divide-y border">
      {faqs.map((faq, i) => {
        const open = expandedFaq === i
        return (
          <div key={faq.question}>
            <button
              type="button"
              onClick={() => setExpandedFaq(open ? null : i)}
              className="flex w-full items-center justify-between gap-4 px-4 py-5 text-left transition-colors hover:bg-gray-50 md:px-6 dark:hover:bg-neutral-900"
              aria-expanded={open}
            >
              <span className="text-charcoal-700 text-sm font-medium md:text-base dark:text-neutral-100">
                {faq.question}
              </span>
              <span
                className={cn(
                  "text-brand shrink-0 text-lg leading-none transition-transform",
                  open && "rotate-45",
                )}
                aria-hidden
              >
                +
              </span>
            </button>
            {open ? (
              <div className="border-divide border-t px-4 py-4 text-sm leading-relaxed text-gray-600 md:px-6 dark:text-neutral-400">
                {faq.answer}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
