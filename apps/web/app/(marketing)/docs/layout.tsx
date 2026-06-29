import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Documentation",
  description:
    "Gravitre documentation: guides, API references, and tutorials for building, deploying, and governing AI agents and workflows.",
  ogDescription: "Guides, API references, and tutorials for building and governing AI agents.",
})

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children
}
