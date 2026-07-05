import { marketingMetadata } from "@/lib/seo"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata = marketingMetadata({
  title: "Documentation",
  description: MARKETING_COPY.docs.description,
  ogDescription: "Guides for GIBE, Gravitre AI, connectors, workflows, and API.",
})

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children
}
