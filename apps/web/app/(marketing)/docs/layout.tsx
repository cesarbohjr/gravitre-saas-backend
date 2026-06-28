import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Documentation",
  description:
    "Gravitre documentation: guides, API references, and tutorials for building, deploying, and governing AI agents and workflows.",
  openGraph: {
    title: "Documentation · Gravitre",
    description: "Guides, API references, and tutorials for building and governing AI agents.",
  },
}

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children
}
