import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Guides",
  description:
    "Step-by-step Gravitre tutorials for your first agent, workflows, integrations, and best practices — linked to live product documentation.",
  ogDescription: "Marketing guides that route to Gravitre docs and how-to articles.",
})

export default function GuidesLayout({ children }: { children: React.ReactNode }) {
  return children
}
