import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Gravitre Terms of Service and Usage",
  canonical: "/terms",
  description: "Read the Gravitre terms of service, including account responsibilities, acceptable use, subscriptions, and conditions for using the platform.",
})

export default function TermsLayout({ children }: { children: React.ReactNode }) {
  return children
}
