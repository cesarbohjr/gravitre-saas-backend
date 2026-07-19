import { marketingMetadata } from "@/lib/seo"
import { TechnologyPage } from "@/components/marketing/features/technology-page"

export const metadata = marketingMetadata({
  title: "Technology — GIBE & Governance",
  description:
    "GIBE (Gravitre Intelligent Business Engine): org-scoped learning, a built-in ML catalog, and predictive ops — paired with human-in-the-loop approval, audit trails, and RBAC.",
  ogDescription:
    "An MCP server with a brain — memory, ML catalog, failure predictions, and governed execution.",
})

export default function TechnologyRoute() {
  return <TechnologyPage />
}
