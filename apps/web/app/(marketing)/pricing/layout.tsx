import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Simple, transparent pricing for teams of every size. Start free and scale to enterprise with governance, federation, and usage-based plans.",
  openGraph: {
    title: "Pricing · Gravitre",
    description:
      "Simple, transparent pricing for teams of every size. Start free and scale to enterprise.",
  },
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
