import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.insights.title} | Gravitre`,
  SURFACE_COPY.insights.description,
  { canonical: "/intelligence" },
)

import { IntelligenceLayoutClient } from "@/components/intelligence/shell/intelligence-layout-client"

export default function IntelligenceLayout({ children }: { children: React.ReactNode }) {
  return <IntelligenceLayoutClient>{children}</IntelligenceLayoutClient>
}
