import { marketingMetadata } from "@/lib/seo"

const aboutMetadata = marketingMetadata({
  title: "About · Gravitre - One AI brain for your business",
  canonical: "/about",
  description:
    "Gravitre builds one AI brain for your entire business — shared intelligence across agents, workflows, connectors, and approvals.",
  ogDescription: "One AI brain for business. Shared intelligence. Governed execution.",
})

export const metadata = { ...aboutMetadata, title: { absolute: "About · Gravitre - One AI brain for your business" } }

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return children
}
