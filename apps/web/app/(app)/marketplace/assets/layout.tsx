import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Marketplace catalog | Gravitre",
  "Browse marketplace assets.",
  { canonical: "/marketplace/assets" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
