import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Gravitre Product Roadmap and Updates",
  canonical: "/roadmap",
  description: "Review the Gravitre product roadmap, including shipped capabilities and planned improvements to agents, workflows, security, and collaboration.",
})

export default function RoadmapLayout({ children }: { children: React.ReactNode }) {
  return children
}
