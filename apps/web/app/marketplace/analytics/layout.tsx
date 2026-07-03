import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Marketplace analytics | Gravitre",
  "Catalog adoption and usage.",
  { canonical: "/marketplace/analytics" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
