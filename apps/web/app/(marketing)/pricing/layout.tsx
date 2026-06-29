import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Pricing",
  description:
    "Simple, transparent pricing for teams of every size. Start free and scale to enterprise with governance, federation, and usage-based plans.",
  ogDescription: "Simple, transparent pricing for teams of every size. Start free and scale to enterprise.",
})

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
