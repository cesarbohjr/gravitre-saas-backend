import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Federation | Gravitre",
  "Cross-org federation settings.",
  { canonical: "/settings/federation" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
