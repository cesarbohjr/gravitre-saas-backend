import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Features",
  description:
    "One AI brain across Gravitre AI, agents, workflows, connectors, approvals, and GIBE — governed execution for your entire business.",
  ogDescription: "Real product surfaces for one shared intelligence — not another AI silo.",
})

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
