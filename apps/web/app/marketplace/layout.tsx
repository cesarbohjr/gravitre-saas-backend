import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Marketplace | Gravitre",
  "Browse and install department packs and AI assets.",
  { canonical: "/marketplace" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
