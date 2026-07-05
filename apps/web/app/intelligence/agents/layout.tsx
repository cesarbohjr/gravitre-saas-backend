import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.hubLinks.agents.title} | Gravitre`,
  SURFACE_COPY.hubLinks.agents.summary,
  { canonical: "/intelligence/agents" },
)

export default function IntelligenceAgentsLayout({ children }: { children: React.ReactNode }) {
  return children
}
