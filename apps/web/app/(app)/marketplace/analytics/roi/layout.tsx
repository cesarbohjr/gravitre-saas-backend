import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Marketplace ROI | Gravitre",
  "Estimated ROI from installed packs.",
  { canonical: "/marketplace/analytics/roi" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
