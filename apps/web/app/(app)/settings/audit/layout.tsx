import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Audit trail | Gravitre",
  "Who did what, when, and how it turned out.",
  { canonical: "/settings/audit" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
