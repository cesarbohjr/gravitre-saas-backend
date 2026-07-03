import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Intelligence Center | Gravitre",
  "See what Gravitre knows, why recommendations were made, and how agents and models perform.",
  { canonical: "/intelligence" },
)

export default function IntelligenceLayout({ children }: { children: React.ReactNode }) {
  return children
}
