import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Features",
  description:
    "GIBE (Gravitre Intelligent Business Engine): built-in ML, org learning, predictive ops, connector executability, agents, workflows, and MCP-native execution with approval gates.",
  ogDescription:
    "An MCP server with a brain — memory, ML catalog, failure predictions, and governed execution.",
})

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return children
}
