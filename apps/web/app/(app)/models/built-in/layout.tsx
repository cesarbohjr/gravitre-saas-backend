import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = authenticatedMetadata(
  `${SURFACE_COPY.builtInModels.title} | Gravitre`,
  SURFACE_COPY.builtInModels.description,
  { canonical: "/models/built-in" },
)

export default function BuiltInModelsLayout({ children }: { children: React.ReactNode }) {
  return children
}
