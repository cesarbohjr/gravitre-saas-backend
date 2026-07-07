import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.learning.title} | Gravitre`,
  SURFACE_COPY.learning.description,
  { canonical: "/intelligence/learning" },
)

export default function LearningLayout({ children }: { children: React.ReactNode }) {
  return children
}
