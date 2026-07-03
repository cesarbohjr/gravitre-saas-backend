import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Multi-Agent Run | Gravitre",
  "Coordinate multiple AI agents on parallel subtasks and merge their results into one recommendation.",
  { canonical: "/multi-agent-run" },
)

export default function MultiAgentRunLayout({ children }: { children: React.ReactNode }) {
  return children
}
