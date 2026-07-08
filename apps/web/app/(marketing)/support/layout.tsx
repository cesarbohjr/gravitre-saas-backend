import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Support",
  description:
    "Search Gravitre help articles, FAQs, and documentation links for agents, workflows, connectors, billing, and security.",
  ogDescription: "Help center links to Gravitre docs, FAQs, and contact support.",
})

export default function SupportLayout({ children }: { children: React.ReactNode }) {
  return children
}
