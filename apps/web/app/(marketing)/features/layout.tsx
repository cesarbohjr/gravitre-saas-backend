import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Features",
  description:
    "Agents, workflows, connectors, learning, and models — one stack with governance built in. Explore the Gravitre platform, its technology (GIBE + governance), and the marketplace.",
  ogDescription:
    "An MCP server with a brain — memory, ML catalog, failure predictions, and governed execution.",
})

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
