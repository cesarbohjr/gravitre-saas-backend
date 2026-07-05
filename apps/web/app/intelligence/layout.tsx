import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.insights.title} | Gravitre`,
  SURFACE_COPY.insights.description,
  { canonical: "/intelligence" },
)

export default function IntelligenceLayout({ children }: { children: React.ReactNode }) {
  return children
}
