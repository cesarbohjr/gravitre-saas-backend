import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "About",
  description:
    "Gravitre builds one AI brain for your entire business — shared intelligence across agents, workflows, connectors, and approvals.",
  ogDescription: "One AI brain for business. Shared intelligence. Governed execution.",
})

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return children
}
