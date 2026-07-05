import { marketingMetadata } from "@/lib/seo"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata = marketingMetadata({
  title: "Pricing",
  description:
    "Plans with the Intelligence Engine included — connector executability, Insights, Learning, and governed execution. Start free, scale to Command.",
  ogDescription: MARKETING_COPY.pricing.subhead,
})

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
