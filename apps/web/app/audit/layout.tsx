import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "History | Gravitre",
  "Audit trail of workspace actions and changes.",
  { canonical: "/audit" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
