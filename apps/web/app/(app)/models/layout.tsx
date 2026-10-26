import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { IntelligenceOverlaysProvider } from "@/components/intelligence/overlays/intelligence-overlays"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.models.title} | Gravitre`,
  SURFACE_COPY.models.description,
  { canonical: "/models" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return <IntelligenceOverlaysProvider>{children}</IntelligenceOverlaysProvider>
}
