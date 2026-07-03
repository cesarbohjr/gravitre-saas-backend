import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Approvals | Gravitre",
  "Review and action pending approval requests.",
  { canonical: "/approvals" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
