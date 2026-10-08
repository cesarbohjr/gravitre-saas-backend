import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Publisher billing | Gravitre",
  "Marketplace earnings and pricing.",
  { canonical: "/marketplace/billing" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
